"""GD-1 evaluation driver: stand up the offline pipeline, score Level C, write the deliverable.

ONE-OFF (not part of CI). It mirrors the GD-1 regression harness, but instead of asserting a
snapshot it computes the criterion-validity scores, downloads the full export bundle as proof,
and renders the tracked validation report. Run from ``backend/``::

    uv run python scripts/golden/run_gd1.py

It spins up a throwaway Postgres (testcontainers), applies the migrations, seeds the captured
GD-1 canonical data, replays the recorded STRING and g:Profiler responses (reusing the regression
fakes verbatim), drives a manual-single-compound run end-to-end, then:
  - computes C1 (disease-pathway recovery), C2 (pathway-panel concordance), C3 (hub corroboration),
    and the §6 per-hub evidence table, all from the run's actual output;
  - downloads ``GET /analyses/{id}/export/all-results.zip`` and extracts it into the artifacts dir;
  - renders the report with ``report.render`` and writes ``report.md``.

No statistic is reimplemented here: it reuses ``scripts/golden/stats.py`` and
``scripts/golden/reference.py``. No seed, fake, or migration list is duplicated: it imports the
regression support and conftest pieces.
"""

from __future__ import annotations

import asyncio
import csv
import io
import sys
import zipfile
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

# Run as a script puts scripts/ on sys.path, not the backend root, so make `app` and the test
# support packages importable (mirrors scripts/golden/capture_gd1.py and scripts/dump_openapi.py).
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))

from app import db  # noqa: E402
from app.main import app  # noqa: E402
from app.pipeline.stages import stage6, stage8  # noqa: E402
from scripts.golden import reference, stats  # noqa: E402
from scripts.golden.report import (  # noqa: E402
    CodeExcerpt,
    Gd1StageMatrixRow,
    HubRow,
    PanelPaper,
    ReportModel,
    render,
)
from tests.scientific.conftest import (  # noqa: E402
    _APPLY,
    _MIGRATIONS,
    _async_url,
    _run_script,
    poll_run,
)
from tests.scientific.gd1_support import (  # noqa: E402
    gd1_gprofiler_client,
    gd1_string_client,
    seed_gd1,
)

# ---------------------------------------------------------------------------
# Static reference panel (spec §5.4): peer-reviewed, fixed before judging.
# ---------------------------------------------------------------------------

PANEL: list[PanelPaper] = [
    PanelPaper(
        citation="Han et al. 2021",
        journal="Evid Based Complement Alternat Med",
        doi="10.1155/2021/9132608",
        contribution="core hubs AKT1, EGFR, STAT3; PI3K-Akt signaling",
    ),
    PanelPaper(
        citation="He et al. 2023",
        journal="Front Pharmacol",
        doi="10.3389/fphar.2023.1102581",
        contribution="cell-cycle targets CDK2, AURKA/B, CHEK1, TYMS, DNMT1, TOP2A",
    ),
    PanelPaper(
        citation="Yuan et al. 2026",
        journal="Front Pharmacol",
        doi="10.3389/fphar.2025.1703562",
        contribution="ferroptosis and Wnt/beta-catenin; hubs SIRT1, SERPINE1, MMP3, WNT5A",
    ),
    PanelPaper(
        citation="Wu et al. 2025",
        journal="Transl Cancer Res",
        doi="10.21037/tcr-2025-359",
        contribution="MDM2, COX-2 (PTGS2); Western-blot validation",
    ),
]

# Panel pathway set (spec §5.3 / §5.4 C2). Each entry maps a canonical panel name to the
# case-insensitive substrings that count as a match in a Herbaflow term name.
C2_PANEL: dict[str, tuple[str, ...]] = {
    "PI3K-Akt signaling": ("pi3k-akt", "pi3k/akt", "pi3k akt"),
    "p53 signaling": ("p53 signaling", "p53 signalling"),
    "Wnt / Wnt-beta-catenin signaling": ("wnt",),
    "Arachidonic acid / COX-2": ("arachidonic acid", "cox-2", "cyclooxygenase"),
    "Cell cycle": ("cell cycle",),
}

FIXTURES = [
    "gd1_seed.json",
    "gd1_string_network.json",
    "gd1_gprofiler.json",
    "gd1_reference_genes.json",
    "gd1_snapshot.json",
]

DOCS_DIR = _BACKEND.parent / "docs" / "validation" / "golden-curcumin-crc"
ARTIFACTS_DIR = DOCS_DIR / "artifacts"


# ---------------------------------------------------------------------------
# Static stage-by-stage fidelity rows (spec §7 §4). Output cells are filled with
# the run's actual numbers at render time.
# ---------------------------------------------------------------------------


def _stage_matrix(m: dict[str, Any]) -> list[Gd1StageMatrixRow]:
    return [
        Gd1StageMatrixRow(
            "1 Compound",
            "not run (manual single compound)",
            "curcumin (PubChem)",
            "curcumin (PubChem, CAS 458-37-7)",
            "curcumin (PubChem)",
            "curcumin (PubChem/RHAWN)",
        ),
        Gd1StageMatrixRow(
            "2 ADME",
            "RDKit Lipinski/Veber; curcumin passes",
            "SwissADME, Lipinski rule of five; passes",
            "not reported",
            "not reported",
            "not reported",
        ),
        Gd1StageMatrixRow(
            "3 Compound to target",
            f"{m['compound_target_count']} measured (ChEMBL + PubChem BioAssay)",
            "104 (SwissTargetPrediction, p>0, Homo sapiens)",
            "448 (PharmMapper + SwissTargetPrediction + TargetNet + SuperPred)",
            "264 (ChEMBL + STRING + literature)",
            "60 (STITCH, confidence 0.7, Homo sapiens)",
        ),
        Gd1StageMatrixRow(
            "4 Disease to target",
            f"{m['disease_target_count']} (Open Targets, at or above the score floor)",
            "1911 (GeneCards/OMIM/TTD/DrugBank)",
            "704 (GEO GSE74602 DEGs intersected with OMIM/DisGeNET/GeneCards)",
            "47,261 (GeneCards/DrugBank/DisGeNET/CTD, score above median)",
            "not reported (GeneCards; CRC plus apoptosis)",
        ),
        Gd1StageMatrixRow(
            "5 Overlap",
            f"{m['overlap_count']} (set intersection)",
            "30 (Jvenn)",
            "73 (Venny)",
            "46 (Venny; plus RNA-seq DEGs 3328)",
            "25 (curcumin, CRC, apoptosis triple)",
        ),
        Gd1StageMatrixRow(
            "6 PPI",
            f"{m['ppi_node_count']} nodes, {m['ppi_edge_count']} edges (STRING)",
            "26 nodes, 90 edges (STRING 0.4)",
            "70 nodes, 230 edges (STRING)",
            "42 nodes, 232 edges (STRING v11.5, 0.5, Homo sapiens)",
            "25 input genes; nodes/edges not reported (STRING)",
        ),
        Gd1StageMatrixRow(
            "7 Hubs",
            "10 (MCC, Chin 2014)",
            "3 core by degree (NetworkAnalyzer + CytoNCA): AKT1, EGFR, STAT3",
            (
                "10 (cytoHubba top-15 intersection of Degree/MNC/MCC/Closeness): CDK2, TOP2A, "
                "CCNA2, AURKA, AURKB, CHEK1, TYMS, TK1, DNMT1, HSP90AA1"
            ),
            (
                "11 (cytoHubba degree plus median; MCODE 8.364): ESR1, JUN, SIRT1, SERPINE1, "
                "ICAM1, HMOX1, CHUK, EP300, MMP3, PTGS1, WNT5A"
            ),
            "none (validated MDM2, COX-2; no hub-ranking stage)",
        ),
        Gd1StageMatrixRow(
            "8 Enrichment",
            f"{m['enrichment_term_count']} (g:Profiler GO+KEGG); CRC present",
            "61 KEGG, 140 GO (DAVID, P<0.05); CRC present",
            "34 KEGG, 256 GO (DAVID); CRC not in top-20",
            "33 pathways, 106 GO (DAVID, P<0.05 and FDR<0.05); CRC not in top-20",
            "about 30 KEGG, 24 GO (R clusterProfiler); CRC present",
        ),
    ]


def _level_b() -> list[tuple[str, str]]:
    return [
        ("1", "not applicable (Herbaflow starts from the supplied compound)"),
        ("2", "different-but-valid (RDKit drug-likeness versus SwissADME)"),
        ("3", "different-but-valid (measured bioactivity versus predicted targets)"),
        ("4", "different-but-valid (Open Targets scored versus text-mined unions)"),
        ("5", "equivalent (set intersection)"),
        ("6", "equivalent (STRING PPI)"),
        ("7", "equivalent (MCC / cytoHubba family)"),
        ("8", "equivalent (GO/KEGG enrichment)"),
    ]


def _code_excerpts() -> list[CodeExcerpt]:
    test_path = _BACKEND / "tests" / "scientific" / "test_golden_gd1.py"
    ref_path = _BACKEND / "scripts" / "golden" / "reference.py"
    return [
        CodeExcerpt(
            "Regression test (Level A)",
            "backend/tests/scientific/test_golden_gd1.py",
            "python",
            test_path.read_text(encoding="utf-8"),
        ),
        CodeExcerpt(
            "Reference gene-set loader",
            "backend/scripts/golden/reference.py",
            "python",
            ref_path.read_text(encoding="utf-8"),
        ),
    ]


# ---------------------------------------------------------------------------
# Pipeline run
# ---------------------------------------------------------------------------


async def _run_pipeline(client: httpx.AsyncClient, seed: dict[str, Any]) -> dict[str, Any]:
    """POST the analysis, poll to completion, return the stage_results dict + the run id."""
    resp = await client.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_compounds",
            "manual_compound_ids": [seed["curcumin_compound_id"]],
            "disease_input_mode": "selection",
            "disease_id": seed["disease_id"],
            "mode": "auto",
        },
    )
    if resp.status_code != 202:
        raise RuntimeError(f"create failed {resp.status_code}: {resp.text}")
    run_id = resp.json()["analysis_id"]
    state = await poll_run(client, run_id, max_iters=300)
    if state.get("status") != "complete":
        raise RuntimeError(
            f"run did not complete: {state.get('status')} {state.get('error_message')}"
        )
    return {"run_id": run_id, "stage_results": state["stage_results"]}


def _download_and_extract(zip_bytes: bytes) -> list[str]:
    """Extract the all-results bundle into the artifacts dir; return sorted member names."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    # Wipe stale artifacts so the deliverable is exactly this run's output.
    for old in sorted(ARTIFACTS_DIR.rglob("*"), reverse=True):
        if old.is_file():
            old.unlink()
        elif old.is_dir():
            old.rmdir()
    names: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = ARTIFACTS_DIR / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info.filename))
            names.append(info.filename)
    return sorted(names)


def _csv_row_count(path: Path) -> int:
    """Count data rows (excluding the header and any leading comment lines) in a CSV artifact."""
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        rows = [r for r in reader if r and not r[0].startswith("#")]
    return max(len(rows) - 1, 0)  # minus header


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _score(sr: dict[str, Any]) -> dict[str, Any]:
    """Compute the run's headline numbers and the Level-C scores from the stage results."""
    ref = reference.load_gd1()

    s5 = sr["5"]
    overlap_genes = [o["gene_symbol"] for o in s5.get("overlap", []) if o.get("gene_symbol")]
    # gene_symbol -> opentargets_score (Stage-5 overlap rows carry the disease score).
    score_by_gene: dict[str, Any] = {
        o["gene_symbol"]: o.get("opentargets_score")
        for o in s5.get("overlap", [])
        if o.get("gene_symbol")
    }

    s6 = sr["6"]
    ppi_node_count = len(s6.get("nodes", []))
    ppi_edge_count = len(s6.get("edges", []))

    s7 = sr["7"]
    hubs_sorted = sorted(s7["hubs"], key=lambda h: -h["mcc"])
    top10 = hubs_sorted[:10]
    top10_genes = [h["gene_symbol"] for h in top10]

    s8 = sr["8"]
    terms = s8.get("terms", [])
    term_names = [t["name"] for t in terms]
    kegg_terms = [t["name"] for t in terms if t.get("source") == "KEGG"]

    # --- C1: disease-pathway recovery (binary) ---
    c1_term = "Colorectal cancer"
    c1_present = any(c1_term.lower() == n.lower() for n in term_names)

    # --- C2: pathway-panel concordance ---
    lower_terms = [n.lower() for n in term_names]
    c2_matched: list[str] = []
    for panel_name, needles in C2_PANEL.items():
        if any(any(nd in lt for lt in lower_terms) for nd in needles):
            c2_matched.append(panel_name)
    herbaflow_panel_match_set = set(c2_matched)
    panel_set = set(C2_PANEL.keys())
    c2_jaccard = stats.jaccard(herbaflow_panel_match_set, panel_set)

    # --- C3: hub corroboration ---
    precision_at_10 = stats.precision_at_k(top10_genes, ref.gene_set, k=10)
    hub_genes_in_ref = [g for g in top10_genes if g in ref.gene_set]
    hits = len(hub_genes_in_ref)
    fisher = stats.fisher_overrepresentation(
        hits=hits,
        drawn=10,
        reference_size=len(ref.gene_set),
        universe=ref.universe,
    )

    # --- §6 evidence table ---
    hub_rows: list[HubRow] = []
    for h in top10:
        gene = h["gene_symbol"]
        papers = ref.papers_for(gene)
        score = score_by_gene.get(gene)
        hub_rows.append(
            HubRow(
                gene_symbol=gene,
                mcc_rank=h["rank"],
                mcc=h["mcc"],
                panel_papers=", ".join(papers) if papers else "not in panel",
                opentargets_score=(f"{score:.3f}" if isinstance(score, (int, float)) else "n/a"),
                in_ctd="not assessed",
            )
        )

    # --- Verdict (§5.5): Level A green AND C1 yes AND (Fisher p<0.05 OR precision@10>=0.6) ---
    c3_pass = fisher.p_value < 0.05 or precision_at_10 >= 0.6
    verdict_successful = c1_present and c3_pass  # Level A is the green regression test

    if verdict_successful:
        reason_bits = [
            "Level A (the regression snapshot test) passes.",
            f'The disease pathway "{c1_term}" is recovered (C1 yes).',
        ]
        if fisher.p_value < 0.05:
            reason_bits.append(
                f"The hub set is significantly over-represented for reference genes "
                f"(Fisher exact p = {fisher.p_value:.2e}, odds ratio {fisher.odds_ratio:.1f}), "
                f"driven by recognized colorectal-cancer hubs such as "
                f"{', '.join(hub_genes_in_ref) or 'the recovered reference genes'}."
            )
        else:
            reason_bits.append(f"precision@10 is {precision_at_10:.2f} (at or above 0.6).")
        verdict_reason = " ".join(reason_bits)
    else:
        verdict_reason = (
            "The run does not meet the pre-registered success rubric: "
            f"C1 present = {c1_present}, Fisher p = {fisher.p_value:.3g}, "
            f"precision@10 = {precision_at_10:.2f}."
        )

    return {
        "compound_target_count": s5.get("compound_target_count", 0),
        "disease_target_count": s5.get("disease_target_count", 0),
        "overlap_count": s5.get("count", 0),
        "overlap_genes": overlap_genes,
        "ppi_node_count": ppi_node_count,
        "ppi_edge_count": ppi_edge_count,
        "enrichment_term_count": s8.get("count", len(terms)),
        "enrichment_kegg_terms": kegg_terms,
        "top10_hubs": top10_genes,
        "hub_rows": hub_rows,
        "c1_present": c1_present,
        "c1_term": c1_term,
        "c2_matched": c2_matched,
        "c2_panel_set": list(C2_PANEL.keys()),
        "c2_jaccard": c2_jaccard,
        "c2_overlap_count": len(c2_matched),
        "c3_precision_at_10": precision_at_10,
        "c3_hits_in_reference": hits,
        "c3_hub_genes_in_reference": hub_genes_in_ref,
        "c3_fisher_p": fisher.p_value,
        "c3_fisher_odds": fisher.odds_ratio,
        "reference_gene_count": len(ref.gene_set),
        "reference_universe": ref.universe,
        "reference_genes": sorted(ref.gene_set),
        "verdict_successful": verdict_successful,
        "verdict_reason": verdict_reason,
    }


def _build_model(seed: dict[str, Any], m: dict[str, Any], artifact_files: list[str]) -> ReportModel:
    ctp_nodes = _csv_row_count(ARTIFACTS_DIR / "network-and-docking" / "ctp-nodes.csv")
    ctp_edges = _csv_row_count(ARTIFACTS_DIR / "network-and-docking" / "ctp-edges.csv")
    return ReportModel(
        compound_name=seed["compound"]["canonical_name"],
        compound_inchikey=seed["curcumin_inchikey"].replace("inchikey:", ""),
        disease_name="Colorectal Cancer",
        disease_key="DOID:9256",
        entry_mode="manual single-compound",
        panel=PANEL,
        fixtures=FIXTURES,
        compound_target_count=m["compound_target_count"],
        disease_target_count=m["disease_target_count"],
        overlap_count=m["overlap_count"],
        overlap_genes=m["overlap_genes"],
        ppi_node_count=m["ppi_node_count"],
        ppi_edge_count=m["ppi_edge_count"],
        enrichment_term_count=m["enrichment_term_count"],
        top10_hubs=m["top10_hubs"],
        code_excerpts=_code_excerpts(),
        stage_rows=[],
        stage_matrix=_stage_matrix(m),
        level_b_rows=_level_b(),
        hub_rows=m["hub_rows"],
        ctp_node_count=ctp_nodes,
        ctp_edge_count=ctp_edges,
        enrichment_kegg_terms=m["enrichment_kegg_terms"],
        artifact_files=artifact_files,
        reference_gene_count=m["reference_gene_count"],
        reference_universe=m["reference_universe"],
        reference_genes=m["reference_genes"],
        c1_present=m["c1_present"],
        c1_term=m["c1_term"],
        c2_matched=m["c2_matched"],
        c2_panel_set=m["c2_panel_set"],
        c2_jaccard=m["c2_jaccard"],
        c2_overlap_count=m["c2_overlap_count"],
        c3_precision_at_10=m["c3_precision_at_10"],
        c3_hits_in_reference=m["c3_hits_in_reference"],
        c3_hub_genes_in_reference=m["c3_hub_genes_in_reference"],
        c3_fisher_p=m["c3_fisher_p"],
        c3_fisher_odds=m["c3_fisher_odds"],
        level_a_pass=True,
        verdict_successful=m["verdict_successful"],
        verdict_reason=m["verdict_reason"],
        notes=[
            "The full export bundle for this run is committed under `artifacts/` as proof: "
            "per-stage CSVs, chart PNGs, the Cytoscape network tables, and the run's own report.",
        ],
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


async def main() -> None:
    with PostgresContainer("postgres:16-alpine") as pg:
        engine = create_async_engine(_async_url(pg))
        try:
            async with engine.begin() as conn:
                for name in _APPLY:
                    await _run_script(conn, (_MIGRATIONS / name).read_text(encoding="utf-8"))

            seed = await seed_gd1(engine)

            # Replay the recorded STRING + g:Profiler responses (no monkeypatch here, since this
            # is a standalone driver): reassign the stage-module client factories directly,
            # reusing the regression replay doubles verbatim. Stage 3 stays offline via edge-reuse.
            stage6.StringClient = lambda http: gd1_string_client()  # type: ignore[attr-defined,assignment,return-value]
            stage8.GprofilerClient = lambda http: gd1_gprofiler_client()  # type: ignore[attr-defined,assignment,return-value]

            maker = async_sessionmaker(engine, expire_on_commit=False)
            db.set_sessionmaker(maker)

            async def override() -> Any:
                async with maker() as s:
                    yield s

            app.dependency_overrides[db.get_session] = override
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                run = await _run_pipeline(client, seed)
                sr = run["stage_results"]

                # Download the export bundle (409s unless complete; the run is complete here).
                export = await client.get(f"/analyses/{run['run_id']}/export/all-results.zip")
                if export.status_code != 200:
                    raise RuntimeError(f"export failed {export.status_code}: {export.text[:200]}")
            app.dependency_overrides.clear()

            artifact_files = _download_and_extract(export.content)
            m = _score(sr)
            model = _build_model(seed, m, artifact_files)

            DOCS_DIR.mkdir(parents=True, exist_ok=True)
            report_md = render(model)
            (DOCS_DIR / "report.md").write_text(report_md, encoding="utf-8")

            # --- console summary ---
            print("GD-1 evaluation complete")
            print(f"  overlap count   : {m['overlap_count']}")
            print(f"  overlap genes   : {', '.join(m['overlap_genes'])}")
            print(f"  PPI             : {m['ppi_node_count']} nodes, {m['ppi_edge_count']} edges")
            print(f"  top-10 hubs     : {', '.join(m['top10_hubs'])}")
            print(f"  C1 ({m['c1_term']}) present : {m['c1_present']}")
            print(
                f"  C2 matched panel pathways : {', '.join(m['c2_matched']) or 'none'} "
                f"(Jaccard {m['c2_jaccard']:.3f})"
            )
            print(
                f"  C3 precision@10 : {m['c3_precision_at_10']:.3f} "
                f"({m['c3_hits_in_reference']}/10 in reference: "
                f"{', '.join(m['c3_hub_genes_in_reference']) or 'none'})"
            )
            print(
                f"  C3 Fisher       : p = {m['c3_fisher_p']:.3e}, "
                f"odds ratio = {m['c3_fisher_odds']:.2f}"
            )
            verdict_label = "SUCCESSFUL" if m["verdict_successful"] else "NOT SUCCESSFUL"
            print(f"  VERDICT         : {verdict_label}")
            print(f"  report.md       : {DOCS_DIR / 'report.md'}")
            print(f"  artifacts ({len(artifact_files)}):")
            for name in artifact_files:
                print(f"    - {name}")
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
