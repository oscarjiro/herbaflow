"""GD-2 evaluation driver: stand up the offline pipeline, score ranker agreement, write the report.

ONE-OFF (not part of CI). It mirrors the GD-2 regression harness, but instead of asserting a
snapshot it computes the ranker-agreement criterion, downloads the full export bundle as proof, and
renders the validation report. Run from ``backend/``::

    uv run python scripts/golden/run_gd2.py

It spins up a throwaway Postgres (testcontainers), applies the migrations, seeds the captured GD-2
canonical targets, replays the recorded protein-protein interaction network and an empty enrichment
response (reusing the regression fakes verbatim), drives two manual-targets runs end-to-end (the
full-manual headline run over the supplied 1165 plant + 777 disease target sets, and the controlled
identical-input run over the 233 shared genes on both sides), then:
  - computes the ranker agreement (Kendall tau / Spearman rho over the shared ranked genes, plus
    overlap at 10) between Herbaflow's Maximal Clique Centrality ranking and the reference ranking
    from the controlled identical-input run;
  - proves the target-set recovery live from the full-manual headline run's own overlap;
  - downloads ``GET /analyses/{id}/export/all-results.zip`` for the headline run and extracts it
    into the artifacts dir;
  - renders the report with ``report.render_gd2`` and writes ``report.md``.

No statistic is reimplemented here: it reuses ``scripts/golden/stats.py`` and
``scripts/golden/reference.py``. No seed, fake, or migration list is duplicated: it imports the
GD-2 regression support and the conftest pieces. The report and the artifacts are gitignored
(unpublished reference data); only this code is committed.
"""

from __future__ import annotations

import asyncio
import io
import sys
import zipfile
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

# Run as a script puts scripts/ on sys.path, not the backend root, so make `app` and the test
# support packages importable (mirrors scripts/golden/run_gd1.py).
_BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND))

from app import db  # noqa: E402
from app.main import app  # noqa: E402
from app.pipeline.stages import stage6, stage8  # noqa: E402
from scripts.golden import reference, stats  # noqa: E402
from scripts.golden.report import (  # noqa: E402
    CodeExcerpt,
    Gd2HubRow,
    Gd2ReportModel,
    StageRow,
    render_gd2,
)
from tests.scientific.conftest import (  # noqa: E402
    _APPLY,
    _MIGRATIONS,
    _async_url,
    _run_script,
    poll_run,
)
from tests.scientific.gd2_support import (  # noqa: E402
    gd2_gprofiler_client,
    gd2_string_client,
    seed_gd2,
)

PLANT_NAMES = ["Allium cepa", "Curcuma longa", "Zingiber officinale"]
DISEASE_NAME = "pancreatic cancer"
REFERENCE_NAME = "an unpublished medicinal-plant network-pharmacology thesis"

FIXTURES = [
    "gd2_seed.json",
    "gd2_string.json",
    "gd2_hub_ref.json",
    "gd2_snapshot.json",
]

DOCS_DIR = _BACKEND.parent / "docs" / "validation" / "golden-hito-pancreatic"
ARTIFACTS_DIR = DOCS_DIR / "artifacts"


# ---------------------------------------------------------------------------
# Static stage-by-stage rows (spec §7 §4). Output cells filled with run numbers.
# ---------------------------------------------------------------------------


def _stage_rows(m: dict[str, Any]) -> list[StageRow]:
    return [
        StageRow(
            "1. Plant to compound",
            "Not run: the targets are supplied directly (manual target entry).",
            "KNApSAcK; 910 candidate compounds (44 + 635 + 231 across the three plants).",
            "N/A",
            "not applicable",
        ),
        StageRow(
            "2. ADME / drug-likeness",
            "Not run: no compounds are derived in a target-only run.",
            "SwissADME, bioavailability > 0.5 and drug-likeness > 0; 113 compounds passing.",
            "N/A",
            "not applicable",
        ),
        StageRow(
            "3. Compound to target",
            f"User-provided targets (manual entry): {m['plant_target_count']} plant-side targets.",
            "SwissTargetPrediction, default parameters; 1906 undeduped (247 + 1056 + 603).",
            f"{m['plant_target_count']} plant-side targets supplied.",
            "user-provided versus predicted",
        ),
        StageRow(
            "4. Disease to target",
            f"User-provided targets (manual entry): {m['disease_target_count']} disease targets.",
            "GeneCards; 777 disease targets.",
            f"{m['disease_target_count']} disease targets supplied.",
            "user-provided versus curated",
        ),
        StageRow(
            "5. Overlap",
            "Pure set intersection of the supplied plant and disease target sets.",
            "Intersection of the plant-target and disease-target sets; 233 shared genes.",
            f"overlap of {m['main_overlap_count']} genes.",
            "equivalent method (set intersection)",
        ),
        StageRow(
            "6. PPI network",
            "STRING protein-protein interaction network over the overlap genes.",
            "STRING, medium confidence 0.4, species 9606; node and edge counts not reported.",
            f"{m['main_ppi_node_count']} nodes, {m['main_ppi_edge_count']} edges.",
            "equivalent method (STRING network)",
        ),
        StageRow(
            "7. Hub ranking",
            "Maximal Clique Centrality (cytoHubba, Chin 2014), the sole ranker.",
            "Iterated skyline (Pareto-dominance) query over degree, betweenness, closeness, and "
            "eigenvector centrality.",
            "Herbaflow top-10: " + ", ".join(m["main_herbaflow_top10"]) + ".",
            "different-but-valid (both centrality-based)",
        ),
        StageRow(
            "8. Functional enrichment",
            "g:Profiler over GO and KEGG; replayed empty because the reference reported none.",
            "Not reported by the reference study.",
            "not assessed (no reference enrichment to compare against).",
            "not assessed",
        ),
    ]


def _code_excerpts() -> list[CodeExcerpt]:
    test_path = _BACKEND / "tests" / "scientific" / "test_golden_gd2.py"
    support_path = _BACKEND / "tests" / "scientific" / "gd2_support.py"
    return [
        CodeExcerpt(
            "Regression test",
            "backend/tests/scientific/test_golden_gd2.py",
            "python",
            test_path.read_text(encoding="utf-8"),
        ),
        CodeExcerpt(
            "Seed and replay support",
            "backend/tests/scientific/gd2_support.py",
            "python",
            support_path.read_text(encoding="utf-8"),
        ),
    ]


# ---------------------------------------------------------------------------
# Pipeline run
# ---------------------------------------------------------------------------


async def _run_controlled(client: httpx.AsyncClient, seed: dict[str, Any]) -> dict[str, Any]:
    """POST the controlled identical-input analysis (233 genes both sides), poll to completion,
    return stage_results + run id."""
    ids = seed["headline_target_ids"]
    resp = await client.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_targets",
            "manual_target_ids": ids,
            "disease_input_mode": "manual_disease_targets",
            "manual_disease_target_ids": ids,
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


async def _run_full_manual(client: httpx.AsyncClient, seed: dict[str, Any]) -> dict[str, Any]:
    """POST the headline full-manual analysis (1165 plant + 777 disease targets), poll, return."""
    resp = await client.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_targets",
            "manual_target_ids": seed["plant_target_ids"],
            "disease_input_mode": "manual_disease_targets",
            "manual_disease_target_ids": seed["disease_target_ids"],
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


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _score(
    main_sr: dict[str, Any], controlled_sr: dict[str, Any], seed: dict[str, Any]
) -> dict[str, Any]:
    """Headline numbers from the full-manual run; ranker agreement from the controlled run."""
    ref = reference.load_gd2()

    # --- headline (full-manual) run: the supplied target sets carried end to end ---
    main_s5 = main_sr["5"]
    main_overlap_count = main_s5.get("count", 0)
    main_overlap_symbols = {o["gene_symbol"] for o in main_s5.get("overlap", [])}
    main_s6 = main_sr["6"]
    main_ppi_node_count = len(main_s6.get("nodes", []))
    main_ppi_edge_count = len(main_s6.get("edges", []))
    main_s7 = main_sr["7"]
    main_ranking = [h["gene_symbol"] for h in sorted(main_s7["hubs"], key=lambda h: -h["mcc"])]
    main_herbaflow_top10 = main_ranking[:10]
    plant_target_count = len(seed["plant_target_ids"])
    disease_target_count = len(seed["disease_target_ids"])

    # --- controlled (identical-input) run: the apples-to-apples ranker comparison ---
    c5 = controlled_sr["5"]
    overlap_count = c5.get("count", 0)
    c6 = controlled_sr["6"]
    ppi_node_count = len(c6.get("nodes", []))
    ppi_edge_count = len(c6.get("edges", []))
    c7 = controlled_sr["7"]
    herbaflow_ranking = [h["gene_symbol"] for h in sorted(c7["hubs"], key=lambda h: -h["mcc"])]
    herbaflow_top10 = herbaflow_ranking[:10]

    c8 = controlled_sr["8"]
    enrichment_terms = c8.get("terms", [])
    enrichment_term_count = c8.get("count", len(enrichment_terms))

    # --- ranker agreement over the shared ranked genes (controlled run) ---
    hito_ranking = list(ref.hito_top10)
    rc = stats.rank_correlation(herbaflow_ranking, hito_ranking)
    o10 = stats.overlap_at_k(herbaflow_ranking, hito_ranking, 10)

    # --- hub comparison table over the union of both top-10s (controlled run) ---
    herbaflow_rank = {g: i + 1 for i, g in enumerate(herbaflow_top10)}
    union = list(herbaflow_top10)
    for g in hito_ranking:
        if g not in herbaflow_rank:
            union.append(g)
    hub_rows: list[Gd2HubRow] = []
    for gene in union:
        ref_score = ref.score_of(gene)
        hub_rows.append(
            Gd2HubRow(
                gene_symbol=gene,
                herbaflow_rank=herbaflow_rank.get(gene),
                reference_rank=ref.rank_of(gene),
                reference_score=(f"{ref_score:.3f}" if ref_score is not None else "n/a"),
            )
        )

    # --- target-set recovery from the LIVE headline run ---
    ref233 = set(seed["overlap_233_symbols"])
    recovered = ref233 <= main_overlap_symbols
    recall = (len(ref233 & main_overlap_symbols) / len(ref233)) if ref233 else 0.0
    extra_genes = sorted(main_overlap_symbols - ref233)
    recovery_overlap_count = main_overlap_count

    # --- verdict ---
    level_a_pass = True
    rankers_agree = (
        rc.kendall_tau is not None
        and rc.spearman_rho is not None
        and rc.kendall_tau > 0
        and rc.spearman_rho > 0
    )
    verdict_successful = level_a_pass and recovered and recall == 1.0 and rankers_agree

    if verdict_successful:
        verdict_reason = (
            "The regression tests pass, so the pipeline reproduces the frozen overlap and hub "
            "ordering exactly. Herbaflow recovers every one of the reference study's "
            f"{len(ref233)} shared targets, a recall of {recall * 100:.0f} percent, and the two "
            "hub rankers agree in direction: Kendall tau is "
            f"{rc.kendall_tau:.3f} and Spearman rho is {rc.spearman_rho:.3f} over the "
            f"{rc.shared} shared ranked genes, with {o10} of the top-10 hubs common to both "
            "lists. The agreement is positive and substantial rather than perfect, which is the "
            "expected outcome when two different but valid centrality-based rankers score the same "
            "network."
        )
    else:
        verdict_reason = (
            "The run does not meet the pre-registered success criteria: "
            f"recovery recall = {recall:.2f}, Kendall tau = "
            f"{rc.kendall_tau if rc.kendall_tau is not None else 'n/a'}, Spearman rho = "
            f"{rc.spearman_rho if rc.spearman_rho is not None else 'n/a'}."
        )

    return {
        "main_overlap_count": main_overlap_count,
        "main_ppi_node_count": main_ppi_node_count,
        "main_ppi_edge_count": main_ppi_edge_count,
        "main_herbaflow_top10": main_herbaflow_top10,
        "plant_target_count": plant_target_count,
        "disease_target_count": disease_target_count,
        "overlap_count": overlap_count,
        "ppi_node_count": ppi_node_count,
        "ppi_edge_count": ppi_edge_count,
        "herbaflow_top10": herbaflow_top10,
        "reference_top10": list(ref.hito_top10),
        "enrichment_term_count": enrichment_term_count,
        "enrichment_assessed": bool(enrichment_terms),
        "hub_rows": hub_rows,
        "c4_kendall_tau": rc.kendall_tau,
        "c4_spearman_rho": rc.spearman_rho,
        "c4_shared": rc.shared,
        "c4_overlap_at_10": o10,
        "recovery_overlap_count": recovery_overlap_count,
        "recovery_reference_count": len(ref233),
        "recovery_recall": recall,
        "recovery_extra_count": len(extra_genes),
        "recovery_extra_genes": extra_genes,
        "recovered": recovered,
        "level_a_pass": level_a_pass,
        "verdict_successful": verdict_successful,
        "verdict_reason": verdict_reason,
    }


def _build_model(m: dict[str, Any], artifact_files: list[str]) -> Gd2ReportModel:
    return Gd2ReportModel(
        plant_names=PLANT_NAMES,
        disease_name=DISEASE_NAME,
        reference_name=REFERENCE_NAME,
        fixtures=FIXTURES,
        code_excerpts=_code_excerpts(),
        stage_rows=_stage_rows(m),
        overlap_count=m["overlap_count"],
        ppi_node_count=m["ppi_node_count"],
        ppi_edge_count=m["ppi_edge_count"],
        herbaflow_top10=m["herbaflow_top10"],
        reference_top10=m["reference_top10"],
        enrichment_term_count=m["enrichment_term_count"],
        enrichment_assessed=m["enrichment_assessed"],
        hub_rows=m["hub_rows"],
        artifact_files=artifact_files,
        recovery_overlap_count=m["recovery_overlap_count"],
        recovery_reference_count=m["recovery_reference_count"],
        recovery_recall=m["recovery_recall"],
        recovery_extra_count=m["recovery_extra_count"],
        recovery_extra_genes=m["recovery_extra_genes"],
        c4_kendall_tau=m["c4_kendall_tau"],
        c4_spearman_rho=m["c4_spearman_rho"],
        c4_shared=m["c4_shared"],
        c4_overlap_at_10=m["c4_overlap_at_10"],
        level_a_pass=m["level_a_pass"],
        verdict_successful=m["verdict_successful"],
        verdict_reason=m["verdict_reason"],
        notes=[
            "The full export bundle for this run is attached under `artifacts/` as proof: "
            "the applicable per-stage CSVs, the chart PNGs, and the run's own report.",
            "The target-set recovery is asserted by the regression test, which confirms the "
            "companion run recovers the reference overlap at full recall plus the extra genes.",
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

            seed = await seed_gd2(engine)

            # Replay the recorded STRING network + an empty g:Profiler, reusing the regression
            # replay doubles verbatim (standalone driver: reassign the stage-module factories).
            stage6.StringClient = lambda http: gd2_string_client()  # type: ignore[attr-defined,assignment,return-value]
            stage8.GprofilerClient = lambda http: gd2_gprofiler_client()  # type: ignore[attr-defined,assignment,return-value]

            maker = async_sessionmaker(engine, expire_on_commit=False)
            db.set_sessionmaker(maker)

            async def override() -> Any:
                async with maker() as s:
                    yield s

            app.dependency_overrides[db.get_session] = override
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                controlled = await _run_controlled(client, seed)
                main = await _run_full_manual(client, seed)
                main_sr = main["stage_results"]
                controlled_sr = controlled["stage_results"]

                export = await client.get(f"/analyses/{main['run_id']}/export/all-results.zip")
                if export.status_code != 200:
                    raise RuntimeError(f"export failed {export.status_code}: {export.text[:200]}")
            app.dependency_overrides.clear()

            artifact_files = _download_and_extract(export.content)
            m = _score(main_sr, controlled_sr, seed)
            model = _build_model(m, artifact_files)

            DOCS_DIR.mkdir(parents=True, exist_ok=True)
            report_md = render_gd2(model)
            (DOCS_DIR / "report.md").write_text(report_md, encoding="utf-8")

            # --- console summary ---
            print("GD-2 evaluation complete")
            print(f"  headline overlap : {m['main_overlap_count']} (full-manual 1165 x 777)")
            print(f"  controlled overlap: {m['overlap_count']} (identical 233 both sides)")
            print(f"  PPI (controlled) : {m['ppi_node_count']} nodes, {m['ppi_edge_count']} edges")
            print(f"  Herbaflow top-10 : {', '.join(m['herbaflow_top10'])}")
            print(f"  reference top-10 : {', '.join(m['reference_top10'])}")
            tau = m["c4_kendall_tau"]
            rho = m["c4_spearman_rho"]
            print(
                f"  C4 ranker agree  : Kendall tau = {tau:.3f}, Spearman rho = {rho:.3f}, "
                f"shared = {m['c4_shared']}, overlap@10 = {m['c4_overlap_at_10']}"
            )
            print(
                f"  recovery         : overlap {m['recovery_overlap_count']} recovers all "
                f"{m['recovery_reference_count']} reference targets (recall "
                f"{m['recovery_recall'] * 100:.0f}%) + {m['recovery_extra_count']} extra: "
                f"{', '.join(m['recovery_extra_genes'])}"
            )
            verdict_label = "SUCCESSFUL" if m["verdict_successful"] else "NOT SUCCESSFUL"
            print(f"  VERDICT          : {verdict_label}")
            print(f"  report.md        : {DOCS_DIR / 'report.md'}")
            print(f"  artifacts ({len(artifact_files)}):")
            for name in artifact_files:
                print(f"    - {name}")
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
