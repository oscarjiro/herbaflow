"""Pure markdown renderer for the GD-1 validation deliverable.

``render(model) -> str`` turns an already-computed :class:`ReportModel` into the tracked
markdown report. No database, no async, no IO, no statistics: the driver
(``run_gd1.py``) computes every number and hands a fully populated model here. Keeping the
renderer pure means the report is a deterministic function of its inputs and can be unit-tested
without standing up a pipeline.

Prose conventions (project output-copy rule): no em dashes, plain scientific language, no
internal project terminology. Every number the report shows is supplied by the driver from the
actual run, never invented here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PanelPaper:
    """One peer-reviewed study in the reference panel."""

    citation: str
    journal: str
    doi: str
    contribution: str


@dataclass(frozen=True)
class StageRow:
    """One row of the Stage 1 to 8 methodological-fidelity comparison."""

    stage: str
    herbaflow: str
    reference: str
    output: str
    verdict: str


@dataclass(frozen=True)
class HubRow:
    """One row of the top-10 hub evidence table."""

    gene_symbol: str
    mcc_rank: int
    mcc: int
    panel_papers: str
    opentargets_score: str
    in_ctd: str


@dataclass(frozen=True)
class CodeExcerpt:
    """A fenced source excerpt embedded in the implementation section."""

    title: str
    path: str
    language: str
    source: str


@dataclass(frozen=True)
class ReportModel:
    """Everything the renderer needs, all precomputed by the driver."""

    # 1. Overview
    compound_name: str
    compound_inchikey: str
    disease_name: str
    disease_key: str
    entry_mode: str
    panel: list[PanelPaper]
    fixtures: list[str]

    # core run numbers
    compound_target_count: int
    disease_target_count: int
    overlap_count: int
    overlap_genes: list[str]
    ppi_node_count: int
    ppi_edge_count: int
    enrichment_term_count: int
    top10_hubs: list[str]

    # 3. Implementation (read at render time by the driver)
    code_excerpts: list[CodeExcerpt]

    # 4. Stage-by-stage
    stage_rows: list[StageRow]

    # 5. Output comparison
    hub_rows: list[HubRow]
    ctp_node_count: int
    ctp_edge_count: int
    enrichment_kegg_terms: list[str]
    artifact_files: list[str]

    # reference set
    reference_gene_count: int
    reference_universe: int
    reference_genes: list[str]

    # 6. Final evaluation (Level C)
    c1_present: bool
    c1_term: str
    c2_matched: list[str]
    c2_panel_set: list[str]
    c2_jaccard: float
    c2_overlap_count: int
    c3_precision_at_10: float
    c3_hits_in_reference: int
    c3_hub_genes_in_reference: list[str]
    c3_fisher_p: float
    c3_fisher_odds: float

    # 7. Verdict
    level_a_pass: bool
    verdict_successful: bool
    verdict_reason: str

    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _fmt_float(value: float, places: int = 3) -> str:
    """Human-readable float: tiny p-values get scientific notation, the rest fixed-point."""
    if value != value:  # NaN guard
        return "n/a"
    if value != 0.0 and abs(value) < 10 ** (-places):
        return f"{value:.2e}"
    return f"{value:.{places}f}"


def _yes_no(flag: bool) -> str:
    return "yes" if flag else "no"


def _join_or_dash(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


def _section_overview(m: ReportModel) -> str:
    panel_rows = [
        [p.citation, p.journal, f"[{p.doi}](https://doi.org/{p.doi})", p.contribution]
        for p in m.panel
    ]
    parts = [
        "## 1. Overview",
        "",
        (
            f"This report validates the Herbaflow network-pharmacology pipeline on a single, "
            f"well-studied pair: the compound {m.compound_name.title()} "
            f"(InChIKey {m.compound_inchikey}) against {m.disease_name} ({m.disease_key}). "
            f"{m.compound_name.title()} is the defining phytochemical of turmeric (Curcuma longa) "
            f"and a widely studied Indonesian-jamu constituent. The run uses the "
            f"{m.entry_mode} entry mode: the compound is supplied directly and the disease is "
            f"selected from the catalog, so the pipeline starts at compound-target identification "
            f"rather than at plant-to-compound mapping."
        ),
        "",
        (
            "The reference for comparison is a fixed panel of four peer-reviewed "
            f"{m.compound_name.lower()} network-pharmacology studies of colorectal (or colon) "
            "cancer. The panel was fixed before any score was computed. Each study used a "
            "different target-prediction method, so the panel deliberately disagrees with itself; "
            "concordance is therefore measured against the panel as a whole and reported, never "
            "asserted against any single paper."
        ),
        "",
        _table(["Study", "Journal", "DOI", "Reported contribution"], panel_rows),
        "",
        "### Fixtures used",
        "",
        (
            "The run is deterministic and offline. It replays recorded external responses so the "
            "result is reproducible and does not depend on the live state of any external service:"
        ),
        "",
    ]
    parts += [f"- `{f}`" for f in m.fixtures]
    return "\n".join(parts)


def _section_methodology(m: ReportModel) -> str:
    return "\n".join(
        [
            "## 2. Evaluation methodology",
            "",
            (
                "The evaluation framework is pre-registered: it was fixed before any number was "
                "judged, to avoid tuning the criteria so the result passes. It composes two "
                "recognized methodologies. The regression layer uses golden-master "
                "(characterization) testing, which captures the pipeline's current output on "
                "frozen inputs and asserts it stays stable. The scientific layer uses "
                "criterion-validity assessment, which measures the agreement of a new instrument "
                "with an accepted reference using standard agreement statistics."
            ),
            "",
            "The framework has three levels:",
            "",
            (
                "- **Level A: structural and regression integrity.** A hard pass or fail. All "
                "applicable stages are present and well-formed; the overlap stage is a pure "
                "intersection; the hub stage ranks by Maximal Clique Centrality in descending "
                "order; and re-running on the frozen inputs reproduces the identical overlap set "
                "and hub ordering. This is the only layer wired to continuous integration."
            ),
            (
                "- **Level B: methodological fidelity.** A recorded judgment, per stage, of how "
                "Herbaflow's method relates to the reference's, drawn from {equivalent, stricter, "
                "different-but-valid, not applicable}. This is documented, not scored."
            ),
            (
                "- **Level C: scientific concordance.** The criterion-validity scores (C1, C2, "
                "C3). These are computed and reported. They are never bound to continuous "
                "integration, because a future paper may revise the reference."
            ),
            "",
            "The pre-registered verdict rubric: a test is successful when Level A passes, and the "
            "disease's own pathway is recovered (C1 yes), and the hub set is significantly "
            "over-represented for reference genes (Fisher exact p < 0.05) or precision@10 is at "
            "least 0.6.",
        ]
    )


def _section_implementation(m: ReportModel) -> str:
    parts = [
        "## 3. Implementation",
        "",
        (
            "The regression test seeds the captured canonical data into a throwaway Postgres "
            "instance, replays the recorded external responses, drives a single-compound run "
            "through all applicable stages, and asserts a frozen snapshot of the scientific "
            "output (overlap count, hub ranking, recovered pathway). The reference gene set is "
            "loaded from a curated fixture assembled from the panel papers. The two source files "
            "below are reproduced verbatim."
        ),
        "",
    ]
    for ex in m.code_excerpts:
        parts += [
            f"### {ex.title}",
            "",
            f"`{ex.path}`",
            "",
            f"```{ex.language}",
            ex.source.rstrip("\n"),
            "```",
            "",
        ]
    return "\n".join(parts).rstrip("\n")


def _section_stage_comparison(m: ReportModel) -> str:
    rows = [[r.stage, r.herbaflow, r.reference, r.output, r.verdict] for r in m.stage_rows]
    return "\n".join(
        [
            "## 4. Stage-by-stage comparison (Stage 1 to 8)",
            "",
            (
                "Each row records how Herbaflow's method for that stage relates to the panel's, "
                "with the Level-B judgment in the final column. The most important distinction is "
                "at compound-target identification: Herbaflow derives compound targets from "
                "measured bioactivity (ChEMBL and PubChem BioAssay), while the panel studies "
                "derive them from target-prediction software (SwissTargetPrediction, PharmMapper). "
                "This is a different but equally valid sourcing choice, and it is the main reason "
                "Herbaflow's hub list differs from any single panel paper's hub list."
            ),
            "",
            _table(
                [
                    "Stage",
                    "Herbaflow: method, tool, source, algorithm",
                    "Reference: same",
                    "Output comparison",
                    "Verdict",
                ],
                rows,
            ),
        ]
    )


def _section_output_comparison(m: ReportModel) -> str:
    hub_rows = [
        [
            h.gene_symbol,
            str(h.mcc_rank),
            str(h.mcc),
            h.panel_papers,
            h.opentargets_score,
            h.in_ctd,
        ]
        for h in m.hub_rows
    ]
    parts = [
        "## 5. Output comparison",
        "",
        "### Overlap (candidate therapeutic targets)",
        "",
        (
            f"Herbaflow intersects {m.compound_target_count} measured compound targets with "
            f"{m.disease_target_count} disease targets (Open Targets association score at or above "
            f"the default floor) to give an overlap of {m.overlap_count} genes: "
            f"{_join_or_dash(m.overlap_genes)}. The panel papers report overlaps of comparable "
            "size from their own predicted target sets; the exact membership differs because the "
            "input universes differ (measured versus predicted)."
        ),
        "",
        "### Hub genes (Maximal Clique Centrality)",
        "",
        (
            f"The protein-protein interaction network over the overlap has {m.ppi_node_count} "
            f"nodes and {m.ppi_edge_count} edges. The top-10 hubs by Maximal Clique Centrality "
            "(the cytoHubba method, Chin et al. 2014), with independent corroboration per hub:"
        ),
        "",
        _table(
            [
                "Hub",
                "MCC rank",
                "MCC score",
                "Reported by panel paper(s)",
                "Open Targets CRC score",
                "In CTD curcumin-CRC",
            ],
            hub_rows,
        ),
        "",
        (
            "The CTD (Comparative Toxicogenomics Database) cross-check is a deferred open item: "
            'each hub is marked "not assessed" rather than guessed. The Open Targets colorectal '
            "cancer association score is the value Herbaflow already stores for each disease "
            "target."
        ),
        "",
        "### Compound-target-pathway network versus the reference drug-target-pathway network",
        "",
        (
            f"Herbaflow's exported compound-target-pathway network has {m.ctp_node_count} nodes "
            f"and {m.ctp_edge_count} edges, connecting the compound to its overlap targets and "
            "those targets to the enriched pathways. The panel papers present an analogous "
            "drug-target-pathway (or compound-target-pathway) figure; the structure is the same "
            "(a tripartite compound, target, pathway graph), the size differs with each paper's "
            "target set. The full node and edge lists are attached as Cytoscape-importable CSVs."
        ),
        "",
        "### Enrichment pathways",
        "",
        (
            f"Functional enrichment returns {m.enrichment_term_count} significant terms. The KEGG "
            f"pathways include: {_join_or_dash(m.enrichment_kegg_terms)}. The presence of the "
            f'"{m.c1_term}" KEGG pathway is the disease-pathway recovery check (C1).'
        ),
    ]
    return "\n".join(parts)


def _section_final_evaluation(m: ReportModel) -> str:
    c2_matched = _join_or_dash(m.c2_matched)
    parts = [
        "## 6. Final evaluation (Level C scores)",
        "",
        "### C1: disease-pathway recovery (binary)",
        "",
        (
            f"Is the disease's own KEGG pathway present in the enrichment result? "
            f'"{m.c1_term}" present: **{_yes_no(m.c1_present)}**.'
        ),
        "",
        "### C2: pathway-panel concordance",
        "",
        (
            "Overlap and Jaccard index between Herbaflow's significant pathways and the panel's "
            f"reported pathway set ({_join_or_dash(m.c2_panel_set)}). Matched panel pathways: "
            f"{c2_matched} ({m.c2_overlap_count} of {len(m.c2_panel_set)}). "
            f"Jaccard index: **{_fmt_float(m.c2_jaccard)}**."
        ),
        "",
        "### C3: hub corroboration",
        "",
        (
            f"Over Herbaflow's top-10 Maximal Clique Centrality hubs against the "
            f"{m.reference_gene_count}-gene curated reference set:"
        ),
        "",
        (
            f"- precision@10 = **{_fmt_float(m.c3_precision_at_10)}** "
            f"({m.c3_hits_in_reference} of 10 hubs are reference genes: "
            f"{_join_or_dash(m.c3_hub_genes_in_reference)})."
        ),
        (
            f"- one-sided Fisher exact test of over-representation: p = "
            f"**{_fmt_float(m.c3_fisher_p)}**, odds ratio = **{_fmt_float(m.c3_fisher_odds, 2)}**. "
            f"The universe is the human protein-coding genome ({m.reference_universe:,} genes), "
            f"stated explicitly; the reference set is {m.reference_gene_count} genes; the draw is "
            "the 10 hubs."
        ),
    ]
    return "\n".join(parts)


def _section_verdict(m: ReportModel) -> str:
    verdict = "SUCCESSFUL" if m.verdict_successful else "NOT SUCCESSFUL"
    parts = [
        "## 7. Verdict",
        "",
        f"**{verdict}**",
        "",
        m.verdict_reason,
        "",
        (
            "Honest note on hub-level divergence. Herbaflow derives compound targets from measured "
            "bioactivity, while the panel papers derive them from target-prediction software. The "
            "two input universes differ by construction, so an exact hub-for-hub match with any "
            "single panel paper is not expected and is not the success criterion. The success "
            "criterion is that the hubs Herbaflow recovers are significantly over-represented for "
            "genes the field independently validated, and that the disease's own pathway is "
            "recovered. A low precision@10 against the panel union is expected and reflects this "
            "measured-versus-predicted input difference, not a defect in the pipeline."
        ),
    ]
    if m.notes:
        parts += ["", "### Notes", ""]
        parts += [f"- {n}" for n in m.notes]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# top-level
# ---------------------------------------------------------------------------


def render(model: ReportModel) -> str:
    """Render the full report markdown from a fully populated model."""
    title = (
        f"# Golden-dataset validation: {model.compound_name.title()} " f"and {model.disease_name}"
    )
    intro = (
        "This is a literature-concordance validation of the Herbaflow eight-stage "
        "network-pharmacology pipeline against a fixed panel of peer-reviewed studies. The full "
        "export bundle for the validated run is attached under `artifacts/` as proof."
    )
    sections = [
        title,
        "",
        intro,
        "",
        _section_overview(model),
        "",
        _section_methodology(model),
        "",
        _section_implementation(model),
        "",
        _section_stage_comparison(model),
        "",
        _section_output_comparison(model),
        "",
        _section_final_evaluation(model),
        "",
        _section_verdict(model),
        "",
    ]
    return "\n".join(sections)
