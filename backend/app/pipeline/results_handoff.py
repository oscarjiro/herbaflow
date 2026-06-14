"""Phase-4 results-handoff — pure builders over a complete run's persisted stage_results.

No DB, no async, no external call (Software Lock §4.6a). Each builder takes plain dicts
(the run's ``stage_results`` plus pre-batched entity-attribute lookups) and returns a CSV
string, a markdown string, or zip bytes. The async orchestration + repo fetches live in
``app/services/export.py``; these functions stay pure so they unit-test on fixtures.

Graph scope (EX-6): targets = the Stage-5 overlap (mechanistic core); compounds = those with a
Stage-3 ``compound_targets`` edge into an overlap target; pathways = Stage-8 enriched terms.
"""

from __future__ import annotations

import csv
import io
from typing import Any


# One canonical rule for a target's graph-node id (gene symbol preferred; falls back to the
# UniProt accession, then the raw target_id). Used by BOTH the node and the edge builder so the
# C-T edge endpoints reference the same id the node table declares.
def _target_node_id(row: dict[str, Any]) -> str:
    return str(row.get("gene_symbol") or row.get("uniprot_accession") or row["target_id"])


def _csv(rows: list[tuple[Any, ...]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    for r in rows:
        writer.writerow(["" if v is None else v for v in r])
    return buf.getvalue()


# One canonical rule for a compound's graph-node id. De-UUID'd: the InChIKey is preferred (a stable
# structural identifier), falling back to the human name, then the raw (UUID) compound_id. Used by
# BOTH the node and edge builder so the C-T edge endpoints reference the same id the node declares.
def _compound_node_id(cid: str, compounds_by_id: dict[str, Any]) -> str:
    c = compounds_by_id.get(cid, {})
    return str(c.get("inchi_key") or c.get("name") or cid)


# Shared column order for the C-T-P node + edge CSVs (single source so the headers can't drift).
_CTP_NODE_COLS = (
    "id",
    "label",
    "type",
    "inchikey",
    "smiles",
    "uniprot_accession",
    "is_hub",
    "source",
)
_CTP_EDGE_COLS = ("source", "target", "interaction", "prediction_method", "p_value")


def build_ctp_graph(
    stage_results: dict[str, Any],
    compounds_by_id: dict[str, dict[str, Any]],
    targets_by_id: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Single C-T-P graph-data home: node + edge dicts shared by the CSV builders and the chart.
    Node ids are de-UUID'd (compound=InChIKey, target=gene symbol, pathway=term id); edge endpoints
    reference those same ids (graph-join rule)."""
    overlap = stage_results.get("5", {}).get("overlap", [])
    hubs = stage_results.get("7", {}).get("hubs", [])
    terms = stage_results.get("8", {}).get("terms", [])
    edges = stage_results.get("3", {}).get("compound_targets", [])

    overlap_by_tid = {o["target_id"]: o for o in overlap}
    hub_tids = {h["target_id"] for h in hubs}
    binding_cids = sorted({e["compound_id"] for e in edges if e["target_id"] in overlap_by_tid})

    nodes: list[dict[str, Any]] = []
    for cid in binding_cids:
        c = compounds_by_id.get(cid, {})
        nodes.append(
            {
                "id": _compound_node_id(cid, compounds_by_id),
                "label": c.get("name") or cid,
                "type": "compound",
                "inchikey": c.get("inchi_key") or "",
                "smiles": c.get("smiles") or "",
                "uniprot_accession": "",
                "is_hub": "",
                "source": "",
            }
        )
    for o in overlap:
        nodes.append(
            {
                "id": _target_node_id(o),
                "label": o.get("gene_symbol") or o.get("uniprot_accession") or o["target_id"],
                "type": "target",
                "inchikey": "",
                "smiles": "",
                "uniprot_accession": o.get("uniprot_accession") or "",
                "is_hub": "true" if o["target_id"] in hub_tids else "false",
                "source": "",
            }
        )
    for t in terms:
        nodes.append(
            {
                "id": t["term_id"],
                "label": t.get("name") or t["term_id"],
                "type": "pathway",
                "inchikey": "",
                "smiles": "",
                "uniprot_accession": "",
                "is_hub": "",
                "source": t.get("source") or "",
            }
        )

    overlap_node_ids = {_target_node_id(o) for o in overlap}
    edge_rows: list[dict[str, Any]] = []
    for e in edges:
        tid = e["target_id"]
        if tid not in overlap_by_tid:
            continue
        edge_rows.append(
            {
                "source": _compound_node_id(e["compound_id"], compounds_by_id),
                "target": _target_node_id(overlap_by_tid[tid]),
                "interaction": "compound-target",
                "prediction_method": e.get("prediction_method") or "",
                "p_value": "",
            }
        )
    for t in terms:
        for gene in t.get("intersection", []):
            if gene in overlap_node_ids:
                edge_rows.append(
                    {
                        "source": gene,
                        "target": t["term_id"],
                        "interaction": "target-pathway",
                        "prediction_method": "",
                        "p_value": _fmt_p(t.get("p_value")),
                    }
                )
    return {"nodes": nodes, "edges": edge_rows}


def build_ctp_nodes(
    stage_results: dict[str, Any],
    compounds_by_id: dict[str, dict[str, Any]],
    targets_by_id: dict[str, dict[str, Any]],
) -> str:
    """Cytoscape node table CSV: one row per compound / target / pathway (see build_ctp_graph)."""
    graph = build_ctp_graph(stage_results, compounds_by_id, targets_by_id)
    rows: list[tuple[Any, ...]] = [_CTP_NODE_COLS]
    rows += [tuple(n[c] for c in _CTP_NODE_COLS) for n in graph["nodes"]]
    return _csv(rows)


def build_ctp_edges(
    stage_results: dict[str, Any],
    compounds_by_id: dict[str, dict[str, Any]] | None = None,
    targets_by_id: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Cytoscape edge table CSV (see build_ctp_graph). C-T edges = Stage-3 edges into an overlap
    target (carry the winning prediction_method). T-P edges = each Stage-8 term linked to the
    overlap genes in its ``intersection`` list (carry the term's corrected p_value).

    The graph builder needs the entity dicts to de-UUID compound endpoints; the two are optional
    (default empty) so the existing single-arg caller in ``services/export.py`` keeps working."""
    graph = build_ctp_graph(stage_results, compounds_by_id or {}, targets_by_id or {})
    rows: list[tuple[Any, ...]] = [_CTP_EDGE_COLS]
    rows += [tuple(e[c] for c in _CTP_EDGE_COLS) for e in graph["edges"]]
    return _csv(rows)


def _fmt_p(p: Any) -> str:
    """Full-precision corrected p as a string; empty when absent."""
    return "" if p is None else repr(float(p))


def build_docking_table(
    stage_results: dict[str, Any],
    compounds_by_id: dict[str, dict[str, Any]],
    targets_by_id: dict[str, dict[str, Any]],
) -> str:
    """One row per Stage-7 hub target x binding compound (compounds whose Stage-3 edges include
    that hub). AlphaFold id = the hub's UniProt accession (recovered from targets_by_id; the hub
    row itself does not carry it). Empty hub set / no binding compounds -> header + stated note."""
    hubs = stage_results.get("7", {}).get("hubs", [])
    edges = stage_results.get("3", {}).get("compound_targets", [])

    edges_by_tid: dict[str, list[dict[str, Any]]] = {}
    for e in edges:
        edges_by_tid.setdefault(e["target_id"], []).append(e)

    rows: list[tuple[Any, ...]] = [
        (
            "hub_gene_symbol",
            "hub_uniprot_accession",
            "alphafold_id",
            "compound_name",
            "compound_inchikey",
            "compound_smiles",
            "prediction_method",
        )
    ]
    for h in hubs:
        tid = h["target_id"]
        gene = h.get("gene_symbol") or ""
        acc = targets_by_id.get(tid, {}).get("uniprot_accession") or ""
        for e in edges_by_tid.get(tid, []):
            c = compounds_by_id.get(e["compound_id"], {})
            rows.append(
                (
                    gene,
                    acc,
                    acc,
                    c.get("name") or e["compound_id"],
                    c.get("inchi_key") or "",
                    c.get("smiles") or "",
                    e.get("prediction_method") or "",
                )
            )
    out = _csv(rows)
    if len(rows) == 1:
        out += "# no hub targets with binding compounds for this run\n"
    return out


def _count(stage: dict[str, Any] | None, key: str = "count") -> str:
    if not stage:
        return "N/A"
    return str(stage.get(key, "N/A"))


def build_report(
    run_meta: dict[str, Any],
    params: dict[str, Any],
    stage_results: dict[str, Any],
    labels: dict[str, Any],
) -> str:
    """Human-readable markdown: run identity, opaque B4 input labels (may be N/A), frozen params,
    per-stage counts (N/A where the stage did not run), and labels-only provenance (no
    source_snapshots version checksums — Software Lock §6.4, a documented limitation)."""
    s = stage_results
    plant = labels.get("plant") or "N/A"
    disease = labels.get("disease") or "N/A"
    lines: list[str] = [
        f"# Run report — {run_meta.get('name') or run_meta.get('analysis_id')}",
        "",
        f"- **Run id:** {run_meta.get('analysis_id')}",
        f"- **Mode:** {run_meta.get('mode')}",
        f"- **Created:** {run_meta.get('created_at')}",
        f"- **Completed:** {run_meta.get('completed_at')}",
        "",
        "## Inputs",
        f"- **Plant(s):** {plant}",
        f"- **Disease:** {disease}",
        "",
        "## Frozen parameters",
    ]
    if params:
        for group, vals in params.items():
            if isinstance(vals, dict):
                pretty = ", ".join(f"{k}={v}" for k, v in vals.items())
                lines.append(f"- **{group}:** {pretty}")
    else:
        lines.append("- N/A")
    lines += [
        "",
        "## Per-stage counts",
        f"- Stage 1 compounds: {_count(s.get('1'))}",
        f"- Stage 2 ADME-passed: {_count(s.get('2'))}",
        f"- Stage 3 compound-targets: {_count(s.get('3'))}",
        f"- Stage 4 disease-targets: {_count(s.get('4'))}",
        f"- Stage 5 overlap: {_count(s.get('5'))}",
        f"- Stage 6 PPI nodes: {_count(s.get('6'), 'node_count')}",
        f"- Stage 7 hubs: {_count(s.get('7'))}",
        f"- Stage 8 enriched terms: {_count(s.get('8'))}",
        "",
        "## Provenance",
        "- Point-in-time only: `source_systems` names + per-stage `source_url`s.",
        (
            "- **No source-version checksums**"
            " (the `source_snapshots` table is not built — a documented"
            " limitation: you get *when* data was fetched and a link to the"
            " record, not *which* external release)."
        ),
        "- Fixed scope: human-only (9606); enrichment background = the compound-target universe.",
    ]
    return "\n".join(lines) + "\n"


def build_ppi_graph(stage_results: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """PPI graph data (Stage 6 nodes/edges + Stage 7 hub flag). Node id = gene symbol; STRING edge
    endpoints are already gene symbols (graph-join holds natively)."""
    s6 = stage_results.get("6", {})
    hub_gids = {h.get("gene_symbol") for h in stage_results.get("7", {}).get("hubs", [])}
    nodes = [
        {
            "id": n["gene_symbol"],
            "gene_symbol": n["gene_symbol"],
            "uniprot_accession": n.get("uniprot_accession") or "",
            "is_hub": "true" if n["gene_symbol"] in hub_gids else "false",
        }
        for n in s6.get("nodes", [])
    ]
    edges = [
        {"source": e["source"], "target": e["target"], "confidence": e.get("confidence")}
        for e in s6.get("edges", [])
    ]
    return {"nodes": nodes, "edges": edges}


_PPI_NODE_COLS = ("id", "gene_symbol", "uniprot_accession", "is_hub")


def build_ppi_nodes(stage_results: dict[str, Any]) -> str:
    """Cytoscape node table CSV for the PPI graph (Stage-6 network, Stage-7 hub flag)."""
    g = build_ppi_graph(stage_results)
    rows: list[tuple[Any, ...]] = [_PPI_NODE_COLS]
    rows += [tuple(n[c] for c in _PPI_NODE_COLS) for n in g["nodes"]]
    out = _csv(rows)
    if len(g["nodes"]) == 0:
        out += "# no PPI nodes for this run\n"
    return out


def build_ppi_edges(stage_results: dict[str, Any]) -> str:
    """Cytoscape edge table CSV for the PPI graph (STRING confidence-scored edges)."""
    g = build_ppi_graph(stage_results)
    rows: list[tuple[Any, ...]] = [("source", "target", "confidence")]
    rows += [(e["source"], e["target"], e["confidence"]) for e in g["edges"]]
    out = _csv(rows)
    if len(g["edges"]) == 0:
        out += "# no PPI edges (sparse or empty network)\n"
    return out


# ---------------------------------------------------------------------------
# Per-stage CSV builders (S1–S8) — one CSV per pipeline stage, reusing the on-screen
# column contracts. An empty stage -> header + a `# note` line (no silent blank file).
# ---------------------------------------------------------------------------


def _csv_with_note(header: tuple[str, ...], rows: list[tuple[Any, ...]], empty_note: str) -> str:
    out = _csv([header] + rows)
    if not rows:
        out += f"# {empty_note}\n"
    return out


def _stage1_csv(sr: dict[str, Any], compounds_by_id: dict[str, Any], _t: dict[str, Any]) -> str:
    cols = ("compound", "inchikey", "smiles")
    rows: list[tuple[Any, ...]] = []
    for c in sr.get("1", {}).get("compounds", []):
        if c.get("tag") == "user-removed":
            continue
        meta = compounds_by_id.get(c.get("compound_id"), {})
        rows.append(
            (
                c.get("canonical_name") or meta.get("name") or c.get("compound_id"),
                meta.get("inchi_key") or "",
                meta.get("smiles") or "",
            )
        )
    return _csv_with_note(cols, rows, "no compounds")


# Stage-2 row columns mirror the on-screen ADME CSV (Stage2View.buildCsv) verbatim — flat row
# keys (no `descriptors` nesting), with a `passed` flag splitting the two stored buckets.
_STAGE2_FIELDS = (
    "compound_id",
    "canonical_name",
    "descriptor_source",
    "molecular_weight",
    "logp",
    "hbond_donors",
    "hbond_acceptors",
    "tpsa",
    "rotatable_bonds",
    "qed_score",
    "np_likeness_score",
    "num_ro5_violations",
    "is_pains_positive",
    "source_url",
    "reason",
)


def _stage2_csv(sr: dict[str, Any], _c: dict[str, Any], _t: dict[str, Any]) -> str:
    cols = (
        "compound_id",
        "canonical_name",
        "passed",
        "descriptor_source",
        "molecular_weight",
        "logp",
        "hbond_donors",
        "hbond_acceptors",
        "tpsa",
        "rotatable_bonds",
        "qed_score",
        "np_likeness_score",
        "num_ro5_violations",
        "is_pains_positive",
        "source_url",
        "reason",
    )
    s2 = sr.get("2", {})
    rows: list[tuple[Any, ...]] = []
    for bucket, passed in (("passed", "true"), ("filtered", "false")):
        for r in s2.get(bucket, []):
            rows.append(
                (
                    r.get("compound_id"),
                    r.get("canonical_name") or "",
                    passed,
                    *(r.get(f, "") for f in _STAGE2_FIELDS[2:]),
                )
            )
    return _csv_with_note(cols, rows, "no ADME results")


def _stage3_csv(sr: dict[str, Any], _c: dict[str, Any], _t: dict[str, Any]) -> str:
    cols = ("gene_symbol", "uniprot_accession", "prediction_method", "source_url")
    rows = [
        (
            t.get("gene_symbol") or "",
            t.get("uniprot_accession") or "",
            t.get("prediction_method") or "",
            t.get("source_url") or "",
        )
        for t in sr.get("3", {}).get("targets", [])
        if t.get("tag") != "user-removed"
    ]
    return _csv_with_note(cols, rows, "no compound targets")


def _stage4_csv(sr: dict[str, Any], _c: dict[str, Any], _t: dict[str, Any]) -> str:
    cols = ("gene_symbol", "uniprot_accession", "opentargets_score", "source_url")
    rows = [
        (
            t.get("gene_symbol") or "",
            t.get("uniprot_accession") or "",
            "" if t.get("opentargets_score") is None else t["opentargets_score"],
            t.get("source_url") or "",
        )
        for t in sr.get("4", {}).get("targets", [])
        if t.get("tag") != "user-removed"
    ]
    return _csv_with_note(cols, rows, "no disease targets")


def _stage5_csv(sr: dict[str, Any], _c: dict[str, Any], _t: dict[str, Any]) -> str:
    cols = ("gene_symbol", "uniprot_accession", "opentargets_score")
    rows = [
        (
            o.get("gene_symbol") or "",
            o.get("uniprot_accession") or "",
            "" if o.get("opentargets_score") is None else o["opentargets_score"],
        )
        for o in sr.get("5", {}).get("overlap", [])
    ]
    return _csv_with_note(cols, rows, "no overlap targets")


def _stage6_csv(sr: dict[str, Any], _c: dict[str, Any], _t: dict[str, Any]) -> str:
    # The PPI per-stage CSV is the edge list (nodes ship in the network bundle's PPI pair).
    return build_ppi_edges(sr)


def _stage7_csv(sr: dict[str, Any], _c: dict[str, Any], _t: dict[str, Any]) -> str:
    cols = (
        "rank",
        "gene_symbol",
        "uniprot_accession",
        "degree",
        "betweenness",
        "closeness",
        "eigenvector",
        "composite",
    )
    rows = [tuple(h.get(c, "") for c in cols) for h in sr.get("7", {}).get("hubs", [])]
    return _csv_with_note(cols, rows, "no hub genes")


def _stage8_csv(sr: dict[str, Any], _c: dict[str, Any], _t: dict[str, Any]) -> str:
    cols = (
        "term_id",
        "name",
        "source",
        "p_value",
        "intersection_size",
        "intersection_genes",
    )
    rows: list[tuple[Any, ...]] = []
    for t in sr.get("8", {}).get("terms", []):
        genes = t.get("intersection", [])
        rows.append(
            (
                t["term_id"],
                t.get("name") or "",
                t.get("source") or "",
                _fmt_p(t.get("p_value")),
                len(genes),
                ";".join(genes),
            )
        )
    return _csv_with_note(cols, rows, "no enriched terms (valid completion)")


_STAGE_CSV = {
    1: _stage1_csv,
    2: _stage2_csv,
    3: _stage3_csv,
    4: _stage4_csv,
    5: _stage5_csv,
    6: _stage6_csv,
    7: _stage7_csv,
    8: _stage8_csv,
}


def build_stage_csv(
    stage: int,
    stage_results: dict[str, Any],
    compounds_by_id: dict[str, dict[str, Any]],
    targets_by_id: dict[str, dict[str, Any]],
) -> str:
    """One CSV per pipeline stage (S1–S8), reusing the on-screen column contracts. Empty stage ->
    header + a stated `# note` line. The S6 per-stage CSV is the PPI edge list."""
    return _STAGE_CSV[stage](stage_results, compounds_by_id, targets_by_id)


def build_bundle(*, ctp_nodes: str, ctp_edges: str, docking: str, report: str) -> bytes:
    """In-memory zip of the four artifacts (deterministic file names)."""
    buf = io.BytesIO()
    import zipfile

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ctp-nodes.csv", ctp_nodes)
        zf.writestr("ctp-edges.csv", ctp_edges)
        zf.writestr("docking.csv", docking)
        zf.writestr("report.md", report)
    return buf.getvalue()
