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


def build_ctp_nodes(
    stage_results: dict[str, Any],
    compounds_by_id: dict[str, dict[str, Any]],
    targets_by_id: dict[str, dict[str, Any]],
) -> str:
    """Cytoscape node table: one row per compound / target / pathway node."""
    overlap = stage_results.get("5", {}).get("overlap", [])
    hubs = stage_results.get("7", {}).get("hubs", [])
    terms = stage_results.get("8", {}).get("terms", [])
    edges = stage_results.get("3", {}).get("compound_targets", [])

    overlap_tids = {o["target_id"] for o in overlap}
    hub_tids = {h["target_id"] for h in hubs}
    binding_cids = sorted({e["compound_id"] for e in edges if e["target_id"] in overlap_tids})

    rows: list[tuple[Any, ...]] = [
        ("id", "label", "type", "inchikey", "uniprot_accession", "is_hub", "source")
    ]
    for cid in binding_cids:
        c = compounds_by_id.get(cid, {})
        rows.append((cid, c.get("name") or cid, "compound", c.get("inchi_key") or "", "", "", ""))
    for o in overlap:
        node_id = _target_node_id(o)
        rows.append(
            (
                node_id,
                o.get("gene_symbol") or o.get("uniprot_accession") or o["target_id"],
                "target",
                "",
                o.get("uniprot_accession") or "",
                "true" if o["target_id"] in hub_tids else "false",
                "",
            )
        )
    for t in terms:
        rows.append(
            (
                t["term_id"],
                t.get("name") or t["term_id"],
                "pathway",
                "",
                "",
                "",
                t.get("source") or "",
            )
        )
    return _csv(rows)


def build_ctp_edges(stage_results: dict[str, Any]) -> str:
    """Cytoscape edge table. C-T edges = Stage-3 edges into an overlap target (carry the winning
    prediction_method). T-P edges = each Stage-8 term linked to the overlap genes in its
    ``intersection`` list (carry the term's corrected p_value — g:Profiler returns one corrected
    value; the chosen correction is recorded in stage_results["8"]["correction"])."""
    overlap = stage_results.get("5", {}).get("overlap", [])
    edges = stage_results.get("3", {}).get("compound_targets", [])
    terms = stage_results.get("8", {}).get("terms", [])

    overlap_by_tid = {o["target_id"]: o for o in overlap}
    overlap_node_ids = {_target_node_id(o) for o in overlap}

    rows: list[tuple[Any, ...]] = [
        ("source", "target", "interaction", "prediction_method", "p_value")
    ]
    for e in edges:
        tid = e["target_id"]
        if tid not in overlap_by_tid:
            continue
        rows.append(
            (
                e["compound_id"],
                _target_node_id(overlap_by_tid[tid]),
                "compound-target",
                e.get("prediction_method") or "",
                "",
            )
        )
    for t in terms:
        for gene in t.get("intersection", []):
            if gene in overlap_node_ids:
                rows.append((gene, t["term_id"], "target-pathway", "", _fmt_p(t.get("p_value"))))
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
