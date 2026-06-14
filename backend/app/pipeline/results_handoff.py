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
import zipfile
from typing import Any

from app.pipeline import report


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
            "source_url",
        )
    ]
    for h in hubs:
        tid = h["target_id"]
        gene = h.get("gene_symbol") or ""
        acc = targets_by_id.get(tid, {}).get("uniprot_accession") or ""
        af_url = f"https://alphafold.ebi.ac.uk/entry/{acc}" if acc else ""
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
                    af_url,
                )
            )
    out = _csv(rows)
    if len(rows) == 1:
        out += "# no hub targets with binding compounds for this run\n"
    return out


def build_report(
    run_meta: dict[str, Any],
    params: dict[str, Any],
    stage_results: dict[str, Any],
    labels: dict[str, Any],
    *,
    input_modes: dict[str, Any],
    frontend_url: str,
    figures: list[tuple[str, bool, str]] | None = None,
) -> str:
    """Render the run's research-grade markdown report. Thin delegate — the report model + renderer
    live in ``app.pipeline.report`` (the single home for the run's human-readable science)."""
    model = report.build_report_model(
        run_meta,
        params,
        stage_results,
        labels,
        input_modes=input_modes,
        frontend_url=frontend_url,
        figures=figures or [],
    )
    return report.render_markdown(model)


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


def _term_url(source: str, term_id: str) -> str:
    """Derive a public page URL for a g:Profiler enrichment term from its source + native id.
    g:Profiler embeds the source as a prefix on non-GO ids (e.g. ``KEGG:04020``); GO keeps the
    full ``GO:`` id for QuickGO."""
    if source.startswith("GO"):
        return f"https://www.ebi.ac.uk/QuickGO/term/{term_id}"
    bare = term_id.split(":", 1)[1] if ":" in term_id else term_id
    if source == "KEGG":
        return f"https://www.kegg.jp/entry/{bare}"
    if source == "REAC":
        return f"https://reactome.org/content/detail/{bare}"
    if source == "WP":
        return f"https://www.wikipathways.org/pathways/{bare}"
    return ""


def _stage8_csv(sr: dict[str, Any], _c: dict[str, Any], _t: dict[str, Any]) -> str:
    cols = (
        "term_id",
        "name",
        "source",
        "p_value",
        "intersection_size",
        "intersection_genes",
        "source_url",
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
                _term_url(t.get("source") or "", t["term_id"]),
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


def build_network_readme() -> str:
    return """\
# Network & docking handoff

This folder contains the compound–target–pathway (C-T-P) network in a format ready for
Cytoscape, a static PNG rendering of that network, and a docking-preparation table that pairs
each hub protein with the compounds that bind it.

## Files

- `ctp-nodes.csv` / `ctp-edges.csv` — the C-T-P network (Cytoscape node and edge tables).
- `ctp-network.png` — a static rendering of the network (may be absent for very large networks).
- `ppi-nodes.csv` / `ppi-edges.csv` — the protein–protein interaction (PPI) sub-network
  (Stage 6); useful if you want to visualise only the target layer.
- `docking.csv` — one row per hub protein × binding compound pair, ready to feed into a
  structure-based docking tool (e.g. AutoDock Vina).

## Import the network into Cytoscape (desktop)

1. Open **File → Import Network from File** and choose `ctp-edges.csv`.
   Map `source` and `target` to the source/target node columns; `interaction` is the edge type.
2. Open **File → Import Table from File** and choose `ctp-nodes.csv`, matched on the `id` column.
   This attaches `label`, `type`, `is_hub`, etc. as node attributes you can style by.

The edge endpoint strings equal the node `id` strings, so the join is exact.

## Columns

### ctp-nodes.csv

| Column | Meaning |
|---|---|
| `id` | Node id: compound InChIKey, target gene symbol, or pathway term id (e.g. `GO:0045944`). |
| `label` | Human-readable display name (compound name, gene symbol, or term name). |
| `type` | Node type: `compound`, `target`, or `pathway`. |
| `inchikey` | InChIKey for compound nodes (27-char structural hash); blank otherwise. |
| `smiles` | **SMILES** of the compound (2-D); ligand input for docking. Blank otherwise. |
| `uniprot_accession` | UniProt accession (e.g. `P37231`) for target nodes; blank otherwise. |
| `is_hub` | `true` if this target was ranked as a hub gene (Stage 7); blank for non-target nodes. |
| `source` | Pathway DB source for pathway nodes (e.g. `KEGG`, `GO:BP`, `REAC`); blank otherwise. |

### ctp-edges.csv

| Column | Meaning |
|---|---|
| `source` | Node id of the edge's origin (compound InChIKey or target gene symbol). |
| `target` | Node id of the edge's destination (target gene symbol or pathway term id). |
| `interaction` | `compound-target` (Stage 3 bioactivity) or `target-pathway` (Stage 8). |
| `prediction_method` | Compound–target evidence: `chembl_bioactivity` or `pubchem_bioassay`. |
| `p_value` | Target–pathway edges: BH-corrected enrichment p-value (full precision); else blank. |

### docking.csv

| Column | Meaning |
|---|---|
| `hub_gene_symbol` | Gene symbol of the hub target (Stage 7 top-ranked proteins). |
| `hub_uniprot_accession` | UniProt accession of the hub protein. |
| `alphafold_id` | **AlphaFold** model id (= `hub_uniprot_accession`); predicted 3-D structure. |
| `compound_name` | Common name of the binding compound. |
| `compound_inchikey` | InChIKey of the binding compound (stable structural identifier). |
| `compound_smiles` | **SMILES** of the binding compound — the ligand input for docking. |
| `prediction_method` | Evidence source for the compound–target interaction. |
| `source_url` | AlphaFold model page for the hub protein (links to the predicted structure). |

## How to use docking.csv

Each row in `docking.csv` describes one candidate docking experiment:

- **Protein (receptor)**: download the **AlphaFold** predicted structure for the UniProt accession
  in `hub_uniprot_accession` (the `source_url` column links directly to the model page). Save the
  structure as PDB or mmCIF.
- **Ligand**: the compound's **SMILES** string in `compound_smiles` encodes its 2-D chemical
  structure. Convert it to a 3-D conformer using a tool such as RDKit or OpenBabel, then prepare
  the ligand file in the format your docking tool expects (e.g. PDBQT for AutoDock Vina).
- **Docking**: run your chosen docking tool (e.g. AutoDock Vina) with the AlphaFold receptor
  structure and the prepared ligand. The predicted binding affinity (kcal/mol) is your primary
  output.

The table already filters to hub proteins only — these are the mechanistically central targets
identified by the network analysis, so they are the highest-priority candidates for docking.
"""


def build_stages_readme() -> str:
    return """\
# Per-stage results

One CSV per pipeline stage (always present; an empty stage carries a `# note` line so you know
it ran but produced no rows). PNG charts accompany the stages that generate one.

---

## Stage 1 — Compound resolution

**`stage1_compounds.csv`**

The compounds that entered the pipeline after resolving your plant selection (or manual compound
list) through PubChem.

| Column | Meaning |
|---|---|
| `compound` | Canonical compound name. |
| `inchikey` | IUPAC InChIKey (stable structural identifier, 27 characters). |
| `smiles` | SMILES string encoding the compound's 2-D chemical structure. |

---

## Stage 2 — ADME / drug-likeness filter

**`stage2_adme.csv`**

All compounds that were evaluated for drug-likeness. Both passing and filtered compounds are
included; the `passed` column tells you which bucket each compound fell into.

| Column | Meaning |
|---|---|
| `compound_id` | Internal compound identifier. |
| `canonical_name` | Canonical compound name. |
| `passed` | `true` if the compound passed the ADME gate; `false` if it was filtered out. |
| `descriptor_source` | Where the molecular descriptors came from (e.g. `etl`, `rdkit`). |
| `molecular_weight` | Molecular weight in Da. |
| `logp` | Calculated partition coefficient (lipophilicity). |
| `hbond_donors` | Number of hydrogen-bond donors. |
| `hbond_acceptors` | Number of hydrogen-bond acceptors. |
| `tpsa` | Topological polar surface area (Å²). |
| `rotatable_bonds` | Number of rotatable bonds (flexibility indicator). |
| `qed_score` | Quantitative Estimate of Drug-likeness (0–1; higher = more drug-like). |
| `np_likeness_score` | Natural-product likeness score. |
| `num_ro5_violations` | Number of Lipinski Rule-of-Five violations. |
| `is_pains_positive` | `True` if the compound triggered a PAINS (pan-assay interference) alert. |
| `source_url` | PubChem compound page URL. |
| `reason` | Why a compound was filtered (blank if it passed). |

---

## Stage 3 — Compound → target identification

**`stage3_compound_targets.csv`**

Protein targets with measured or predicted bioactivity against the ADME-passing compounds.
Evidence comes from ChEMBL (measured bioactivities) and PubChem BioAssay (active assay
outcomes).

| Column | Meaning |
|---|---|
| `gene_symbol` | HGNC gene symbol of the target protein. |
| `uniprot_accession` | UniProt accession of the target protein. |
| `prediction_method` | Evidence source: `chembl_bioactivity` or `pubchem_bioassay`. |
| `source_url` | UniProt entry page for the target. |

---

## Stage 4 — Disease → target collection

**`stage4_disease_targets.csv`**

Targets associated with the disease of interest, sourced from the Open Targets database
(ETL-loaded; not a live call).

| Column | Meaning |
|---|---|
| `gene_symbol` | HGNC gene symbol. |
| `uniprot_accession` | UniProt accession. |
| `opentargets_score` | Open Targets association score (0–1; higher = stronger evidence). |
| `source_url` | UniProt entry page for the target. |

---

## Stage 5 — Target overlap (mechanistic core)

**`stage5_overlap.csv`** · **`stage5_venn.png`**

The intersection of Stage 3 and Stage 4 targets — the proteins that are both active against
the plant compounds AND implicated in the disease. This is the mechanistic core of the analysis.

`stage5_venn.png` shows a Venn diagram of the two sets with the overlap highlighted.

| Column | Meaning |
|---|---|
| `gene_symbol` | HGNC gene symbol. |
| `uniprot_accession` | UniProt accession. |
| `opentargets_score` | Open Targets association score carried forward from Stage 4. |

---

## Stage 6 — Protein–protein interaction (PPI) network

**`stage6_ppi_edges.csv`** · **`stage6_ppi_network.png`**

STRING PPI network built over the overlap targets. The per-stage CSV is the edge list
(node metadata ships in the network bundle's `ppi-nodes.csv`).

`stage6_ppi_network.png` shows the network with hub proteins highlighted.

| Column | Meaning |
|---|---|
| `source` | Gene symbol of one interaction partner. |
| `target` | Gene symbol of the other interaction partner. |
| `confidence` | STRING combined interaction score (0–1). |

---

## Stage 7 — Hub gene ranking

**`stage7_hubs.csv`** · **`stage7_hub_bar.png`**

Targets ranked by their centrality in the PPI network using a composite of degree and
betweenness centrality (hub-bottleneck method, Yu 2007). Higher composite = more central.

`stage7_hub_bar.png` shows a bar chart of the top hub genes by composite score.

| Column | Meaning |
|---|---|
| `rank` | Hub rank (1 = highest composite score). |
| `gene_symbol` | HGNC gene symbol. |
| `uniprot_accession` | UniProt accession. |
| `degree` | Normalised degree centrality (fraction of possible connections). |
| `betweenness` | Normalised betweenness centrality (fraction of shortest paths via this node). |
| `closeness` | Normalised closeness centrality. |
| `eigenvector` | Normalised eigenvector centrality (influence weighted by neighbour importance). |
| `composite` | Hub-bottleneck composite score used for ranking. |

---

## Stage 8 — Functional enrichment

**`stage8_enrichment.csv`** · **`stage8_enrichment_<CATEGORY>.png`**

Functional enrichment of the overlap targets against the compound-target universe (custom
background) using g:Profiler (over-representation analysis). Sources include Gene Ontology
(GO:BP / GO:MF / GO:CC), KEGG, Reactome, and WikiPathways.

This is **one combined** `stage8_enrichment.csv` containing results from all sources; the
`source` column distinguishes them (e.g. `GO:BP`, `KEGG`, `REAC`, `WP`). Separate PNG charts
are generated per category: for example `stage8_enrichment_GO:BP.png`, `stage8_enrichment_KEGG.png`,
`stage8_enrichment_REAC.png`, `stage8_enrichment_WP.png` (a category PNG is omitted if it has
no significant terms).

| Column | Meaning |
|---|---|
| `term_id` | Pathway or ontology term identifier (e.g. `GO:0045944`, `KEGG:04151`). |
| `name` | Human-readable term name. |
| `source` | Database source: `GO:BP`, `GO:MF`, `GO:CC`, `KEGG`, `REAC`, or `WP`. |
| `p_value` | BH-corrected enrichment p-value (full precision). |
| `intersection_size` | Number of overlap genes annotated to this term. |
| `intersection_genes` | Semicolon-separated list of those gene symbols. |
| `source_url` | Link to the term's page in its source database. |
"""


def build_root_readme() -> str:
    return (
        "# Herbaflow analysis — full results\n\n"
        "- `report.md` — the human-readable run report.\n"
        "- `network-and-docking/` — the C-T-P network (Cytoscape) + docking pairing table"
        " + network PNG.\n"
        "- `stages/` — one CSV (and chart, where applicable) per pipeline stage.\n\n"
        "See each folder's README for column details and import steps.\n"
    )


def _zip(files: dict[str, str | bytes | None]) -> bytes:
    """Deterministic in-memory zip; None values are skipped (conditional-PNG rule)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            if content is None:
                continue
            zf.writestr(name, content)
    return buf.getvalue()


def build_network_bundle(
    *, ctp_nodes: str, ctp_edges: str, docking: str, network_png: bytes | None, readme: str
) -> bytes:
    """Network-and-docking zip: CSVs always present; PNG only when not None."""
    return _zip(
        {
            "ctp-nodes.csv": ctp_nodes,
            "ctp-edges.csv": ctp_edges,
            "docking.csv": docking,
            "ctp-network.png": network_png,
            "README.md": readme,
        }
    )


def build_stages_bundle(*, stage_files: dict[str, str | bytes | None], readme: str) -> bytes:
    """Per-stage zip: one entry per stage CSV (and chart, where applicable)."""
    return _zip({**stage_files, "README.md": readme})


def build_all_results_bundle(
    *,
    report: str,
    network_files: dict[str, str | bytes | None],
    stage_files: dict[str, str | bytes | None],
) -> bytes:
    """All-results superset zip: report + network-and-docking/ + stages/ subdirectories.

    Embeds a README.md at the root and sub-READMEs in each subdirectory so the bundle is
    self-contained — a reader opening any folder finds column-level documentation without
    needing to consult an external source."""
    files: dict[str, str | bytes | None] = {
        "README.md": build_root_readme(),
        "report.md": report,
        "network-and-docking/README.md": build_network_readme(),
        "stages/README.md": build_stages_readme(),
    }
    for name, content in network_files.items():
        files[f"network-and-docking/{name}"] = content
    for name, content in stage_files.items():
        files[f"stages/{name}"] = content
    return _zip(files)
