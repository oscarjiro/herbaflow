"""Pure report model + markdown renderer (no DB/async/API). The model is the single home for the
run's human-readable science; render_markdown emits the .md now, a PDF renderer can consume the
same model later."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app import contracts
from app.pipeline import entry_modes


@dataclass
class SourceLink:
    name: str
    url: str | None = None


@dataclass
class ParamRow:
    label: str
    value: str
    unit: str | None
    description: str


@dataclass
class PreviewTable:
    caption: str
    columns: list[str]
    rows: list[tuple[str, ...]]


@dataclass
class StageSection:
    n: int
    name: str
    finding: str
    params: list[ParamRow] = field(default_factory=list)
    sources: list[SourceLink] = field(default_factory=list)
    figure: str | None = None
    csv: str | None = None
    preview: PreviewTable | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class ReportModel:
    title: str
    subtitle: str | None
    about: list[str]
    stages: list[StageSection]
    provenance: list[str]
    footer: str


_ACRONYMS = {
    "mw": "MW",
    "logp": "logP",
    "hba": "HBA",
    "hbd": "HBD",
    "tpsa": "TPSA",
    "np": "NP",
    "ppi": "PPI",
    "iea": "IEA",
}
_ENUM = {
    "functional": "functional associations (not just physical binding)",
    "physical": "physical binding only",
    "fdr": "Benjamini-Hochberg FDR",
    "g_SCS": "g:SCS",
    "bonferroni": "Bonferroni",
}
_SOURCE_NAME = {
    "GO:BP": "GO biological process",
    "GO:MF": "GO molecular function",
    "GO:CC": "GO cellular component",
    "KEGG": "KEGG",
    "REAC": "Reactome",
    "WP": "WikiPathways",
}

# Single home for the per-stage bundle CSV slug (the bundle nests stage CSVs under ``stages/``).
# ``services/export.py`` imports this so there is exactly one slug map.
STAGE_CSV_SLUG: dict[int, str] = {
    1: "compounds",
    2: "adme",
    3: "compound_targets",
    4: "disease_targets",
    5: "overlap",
    6: "ppi_edges",
    7: "hubs",
    8: "enrichment",
}
_STAGE_NAMES = {
    1: "Compounds",
    2: "ADME filter",
    3: "Compound targets",
    4: "Disease targets",
    5: "Target overlap",
    6: "PPI network",
    7: "Hub genes",
    8: "Functional enrichment",
}
_STAGE_PARAM_GROUP = {
    2: "adme",
    3: "target",
    4: "disease_targets",
    6: "ppi",
    7: "hub_genes",
    8: "enrichment",
}
_COUNT_KEY = {6: "node_count"}

_ABOUT = [
    "Scope: human proteins only (species 9606).",
    "These are computational predictions to guide research, not clinical conclusions.",
    "Enrichment is tested against the compound-target universe as background.",
]
_PROVENANCE = [
    "Every compound, target, and pathway links back to the public database it came from; "
    "the report records when each source was queried.",
    "Limitation: we capture *when* and *where* data was fetched, not the exact release version "
    "of each external database, so re-running later may differ slightly as sources update.",
]

_STAGE_FIG_RE = re.compile(r"^stage(\d+)")


def humanize_label(key: str) -> str:
    """Turn a snake_case param key into a human label, preserving science acronyms."""
    return " ".join(_ACRONYMS.get(w, w.capitalize()) for w in key.split("_"))


def humanize_value(key: str, value: Any) -> str:
    """Render a param value for human display: bools as Yes/No, enums spelled out, lists named."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(_SOURCE_NAME.get(str(v), str(v)) for v in value)
    if isinstance(value, str):
        return _ENUM.get(value, value)
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def fmt_num(value: Any) -> str:
    """Format a numeric display value: ints get thousands separators; everything else is str()."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def param_rows(group: str, values: dict[str, Any]) -> list[ParamRow]:
    """Build ParamRows for a param group, pulling unit + description from the contract schema."""
    schema = contracts.pipeline_param_bounds(group)
    rows: list[ParamRow] = []
    for k, v in values.items():
        meta = schema.get(k, {})
        rows.append(
            ParamRow(
                humanize_label(k),
                humanize_value(k, v),
                meta.get("unit"),
                meta.get("description", ""),
            )
        )
    return rows


def _source_md(s: SourceLink) -> str:
    return f"[{s.name}]({s.url})" if s.url else s.name


def render_markdown(m: ReportModel) -> str:
    out: list[str] = [f"# {m.title}", ""]
    if m.subtitle:
        out += [f"*{m.subtitle}*", ""]
    if m.about:
        out += ["## About this analysis", ""] + [f"- {a}" for a in m.about] + [""]
    for st in m.stages:
        out.append(f"## Stage {st.n}: {st.name}")
        out += ["", st.finding, ""]
        if st.params:
            out += [
                "**Parameters**",
                "",
                "| Parameter | Value | Description |",
                "| --- | --- | --- |",
            ]
            for p in st.params:
                val = f"{p.value} {p.unit}" if p.unit else p.value
                out.append(f"| {p.label} | {val} | {p.description} |")
            out.append("")
        if st.sources:
            out.append("**Data sources:** " + "; ".join(_source_md(s) for s in st.sources))
            out.append("")
        if st.preview:
            out += [
                f"*{st.preview.caption}*",
                "",
                "| " + " | ".join(st.preview.columns) + " |",
                "| " + " | ".join("---" for _ in st.preview.columns) + " |",
            ]
            out += ["| " + " | ".join(r) + " |" for r in st.preview.rows]
            out.append("")
        if st.notes:
            out += [f"> {n}" for n in st.notes] + [""]
        ptr = []
        if st.figure:
            ptr.append(f"Figure: `{st.figure}`")
        if st.csv:
            ptr.append(f"Full table: `{st.csv}`")
        if ptr:
            out += [" · ".join(ptr), ""]
    if m.provenance:
        out += ["## How to read these results", ""] + [f"- {p}" for p in m.provenance] + [""]
    out += ["---", m.footer, ""]
    return "\n".join(out) + "\n"


def _state_map(input_modes: dict[str, Any]) -> dict[int, str]:
    """The {stage -> state} map for a stored run; empty for pre-entry-modes / unknown modes."""
    plant = (input_modes or {}).get("plant", "selection")
    disease = (input_modes or {}).get("disease", "selection")
    try:
        return entry_modes.stage_state_map(plant, disease)
    except ValueError:
        return {}


def _up_stages(input_modes: dict[str, Any]) -> set[int]:
    """Stages the user supplied directly (their data sources are honest, not computed externals)."""
    return {s for s, st in _state_map(input_modes).items() if st == entry_modes.USER_PROVIDED}


def _na_stages(input_modes: dict[str, Any]) -> set[int]:
    """Stages that do not apply for the chosen modes (e.g. S1/S2 in a manual-targets run)."""
    return {s for s, st in _state_map(input_modes).items() if st == entry_modes.NOT_APPLICABLE}


def _is_up(stage: int, input_modes: dict[str, Any]) -> bool:
    return stage in _up_stages(input_modes)


def _default_name(labels: dict[str, Any], completed_at: Any) -> str:
    """The Herbaflow-branded default report title when the run has no user name."""
    parts = [labels.get("plant"), labels.get("disease")]
    subject = " and ".join(p for p in parts if p) or "Network analysis"
    date = str(completed_at or "")[:10]
    return f"Herbaflow Analysis: {subject}" + (f", {date}" if date else "")


def _plant_phrase(labels: dict[str, Any]) -> str:
    return labels.get("plant") or "the selected plant(s)"


def _csv_pointer(n: int) -> str:
    return f"stages/stage{n}_{STAGE_CSV_SLUG[n]}.csv"


def _figure_index(figures: list[tuple[str, bool, str]]) -> dict[int, str]:
    """Map ``stageN`` -> the included figure for that stage (first-wins). Names without a
    ``stageN`` prefix (e.g. ``ctp-network.png``) map to no stage."""
    idx: dict[int, str] = {}
    for name, included, _reason in figures:
        if not included:
            continue
        match = _STAGE_FIG_RE.match(name)
        if match is None:
            continue
        n = int(match.group(1))
        idx.setdefault(n, name)
    return idx


_NA_TARGETS = "Not applicable: this run started from user-supplied targets."


def _s1_finding(sr: dict[str, Any], labels: dict[str, Any], im: dict[str, Any], _p: Any) -> str:
    if 1 in _na_stages(im):
        return _NA_TARGETS
    n = (sr.get("1") or {}).get("count")
    if _is_up(1, im):
        who = labels.get("plant") or "user input"
        return f"{fmt_num(n)} compounds supplied directly ({who})."
    return (
        f"{fmt_num(n)} candidate compounds catalogued from {_plant_phrase(labels)}: "
        "the phytochemical space screened in this analysis."
    )


def _s2_finding(sr: dict[str, Any], labels: dict[str, Any], im: dict[str, Any], p: Any) -> str:
    s2 = sr.get("2") or {}
    if 2 in _na_stages(im):
        return _NA_TARGETS
    if ((p or {}).get("adme") or {}).get("skip_adme"):
        return (
            f"ADME screening skipped: all {fmt_num(s2.get('count'))} compounds "
            "carried forward unscreened."
        )
    passed = s2.get("passed")
    filtered = s2.get("filtered")
    n_passed: Any
    n_total: Any
    if isinstance(passed, list):
        n_passed = len(passed)
        n_total = n_passed + (len(filtered) if isinstance(filtered, list) else 0)
    else:
        n_passed = n_total = s2.get("count")
    return (
        f"{fmt_num(n_passed)} of {fmt_num(n_total)} compounds passed drug-likeness filtering "
        "(Lipinski + Veber, natural-product exception applied), retaining the orally-plausible "
        "chemical space."
    )


def _s3_finding(sr: dict[str, Any], labels: dict[str, Any], im: dict[str, Any], _p: Any) -> str:
    s3 = sr.get("3") or {}
    if _is_up(3, im):
        return f"{fmt_num(s3.get('count'))} targets supplied directly."
    cov = s3.get("coverage_pct")
    clause = f" (target coverage {cov}%)" if cov is not None else ""
    return (
        f"{fmt_num(s3.get('count'))} protein targets identified across compounds{clause} "
        "via measured bioactivities."
    )


def _s4_finding(sr: dict[str, Any], labels: dict[str, Any], im: dict[str, Any], p: Any) -> str:
    s4 = sr.get("4") or {}
    if 4 in _na_stages(im):
        return _NA_TARGETS
    if _is_up(4, im):
        return f"{fmt_num(s4.get('count'))} disease targets supplied directly."
    min_score = ((p or {}).get("disease_targets") or {}).get("min_score", "N/A")
    disease = labels.get("disease") or "the disease"
    return (
        f"{fmt_num(s4.get('count'))} proteins associated with {disease} "
        f"(Open Targets, association score >= {min_score}): the disease target space."
    )


def _ppi_connectivity(sr: dict[str, Any]) -> tuple[int, int]:
    """Split the PPI nodes into (connected, isolated): isolated = nodes touched by no edge."""
    s6 = sr.get("6") or {}
    ids = [n.get("gene_symbol") for n in s6.get("nodes", [])]
    endpoints: set[Any] = set()
    for e in s6.get("edges", []):
        endpoints.add(e.get("source"))
        endpoints.add(e.get("target"))
    isolated = sum(1 for i in ids if i not in endpoints)
    return len(ids) - isolated, isolated


def _s5_finding(sr: dict[str, Any], labels: dict[str, Any], im: dict[str, Any], _p: Any) -> str:
    s5 = sr.get("5") or {}
    return (
        f"{fmt_num(s5.get('count'))} targets shared between the "
        f"{fmt_num(s5.get('compound_target_count'))} compound targets and "
        f"{fmt_num(s5.get('disease_target_count'))} disease targets. This is the candidate "
        f"mechanistic core where {_plant_phrase(labels)} may act on "
        f"{labels.get('disease') or 'the disease'}."
    )


def _s6_finding(sr: dict[str, Any], labels: dict[str, Any], im: dict[str, Any], _p: Any) -> str:
    connected, isolated = _ppi_connectivity(sr)
    n = (sr.get("6") or {}).get("node_count", connected + isolated)
    return (
        f"The {fmt_num(n)} shared targets form a STRING functional-association network: "
        f"{connected} interconnected, {isolated} isolated. Interconnection suggests a coordinated "
        f"module rather than independent action."
    )


def _s7_finding(sr: dict[str, Any], labels: dict[str, Any], im: dict[str, Any], _p: Any) -> str:
    hubs = sorted(
        (sr.get("7") or {}).get("hubs", []),
        key=lambda h: h.get("composite") or 0.0,
        reverse=True,
    )
    if not hubs:
        return "No hub genes were identified (the shared-target network is too sparse to rank)."
    top = ", ".join(h.get("gene_symbol") or str(h.get("target_id")) for h in hubs[:3])
    return (
        f"Hub-bottleneck ranking (degree + betweenness composite, Yu 2007) prioritises {top} "
        f"as the most topologically central targets, the likely primary mediators."
    )


def _s8_finding(sr: dict[str, Any], labels: dict[str, Any], im: dict[str, Any], _p: Any) -> str:
    terms = [t for t in (sr.get("8") or {}).get("terms", []) if t.get("p_value") is not None]
    if not terms:
        return (
            "No functional enrichment terms reached significance for the shared targets "
            "(a valid result)."
        )
    ordered = sorted(terms, key=lambda t: t["p_value"])
    themes = ", ".join(t.get("name") or t["term_id"] for t in ordered[:3])
    top = ordered[0]
    by_cat: dict[str, int] = {}
    for t in terms:
        c = t.get("source", "?")
        by_cat[c] = by_cat.get(c, 0) + 1
    breakdown = ", ".join(f"{n} {_SOURCE_NAME.get(c, c)}" for c, n in by_cat.items())
    return (
        f"The shared targets are enriched for {themes} ({fmt_num(len(terms))} terms, FDR < 0.05), "
        f"indicating the biological processes through which {_plant_phrase(labels)} may act on "
        f"{labels.get('disease') or 'the disease'}. Strongest: {top.get('name') or top['term_id']} "
        f"(adjusted p = {top['p_value']:.2g}, {len(top.get('intersection', []))} genes). "
        f"By category: {breakdown}."
    )


def _hub_preview(sr: dict[str, Any]) -> PreviewTable | None:
    """Top-5 hub genes by composite score (None when no hubs were ranked)."""
    hubs = (sr.get("7") or {}).get("hubs", [])
    if not hubs:
        return None
    ordered = sorted(hubs, key=lambda h: h.get("composite") or 0.0, reverse=True)[:5]
    rows: list[tuple[str, ...]] = [
        (str(h.get("gene_symbol") or h.get("target_id")), f"{(h.get('composite') or 0.0):.3f}")
        for h in ordered
    ]
    return PreviewTable("Top hub genes", ["Gene", "Composite score"], rows)


def _term_preview(sr: dict[str, Any]) -> PreviewTable | None:
    """Top-5 enriched terms by adjusted p-value (None when no significant terms)."""
    terms = [t for t in (sr.get("8") or {}).get("terms", []) if t.get("p_value") is not None]
    if not terms:
        return None
    ordered = sorted(terms, key=lambda t: t["p_value"])[:5]
    rows: list[tuple[str, ...]] = [
        (
            str(t.get("name") or t["term_id"]),
            str(_SOURCE_NAME.get(t.get("source", "?"), t.get("source", "?"))),
            f"{t['p_value']:.2g}",
            str(len(t.get("intersection", []))),
        )
        for t in ordered
    ]
    return PreviewTable("Top enriched terms", ["Term", "Category", "Adjusted p", "Genes"], rows)


_FINDERS = {
    1: _s1_finding,
    2: _s2_finding,
    3: _s3_finding,
    4: _s4_finding,
    5: _s5_finding,
    6: _s6_finding,
    7: _s7_finding,
    8: _s8_finding,
}


def build_report_model(
    run_meta: dict[str, Any],
    params: dict[str, Any],
    stage_results: dict[str, Any],
    labels: dict[str, Any],
    *,
    input_modes: dict[str, Any],
    frontend_url: str | None,
    figures: list[tuple[str, bool, str]],
) -> ReportModel:
    """Assemble the human-readable report model for a complete run (pure — no DB/async/API)."""
    im = input_modes or {}
    p = params or {}
    fig_for = _figure_index(figures)
    na = _na_stages(im)
    stages: list[StageSection] = []
    for n in range(1, 9):
        finding = _FINDERS[n](stage_results or {}, labels, im, p)
        if n in na:
            stages.append(
                StageSection(
                    n=n,
                    name=_STAGE_NAMES[n],
                    finding=finding,
                    params=[],
                    sources=[],
                    figure=None,
                    csv=None,
                    preview=None,
                    notes=[],
                )
            )
            continue
        group = _STAGE_PARAM_GROUP.get(n)
        gvals = p.get(group) if group else None
        stages.append(
            StageSection(
                n=n,
                name=_STAGE_NAMES[n],
                finding=finding,
                params=(
                    param_rows(group, gvals)
                    if group is not None and isinstance(gvals, dict) and gvals
                    else []
                ),
                sources=[
                    SourceLink(name=str(s["name"]), url=s.get("url"))
                    for s in contracts.stage_sources(n, user_provided=_is_up(n, im))
                ],
                figure=fig_for.get(n),
                csv=_csv_pointer(n),
                preview=(
                    _hub_preview(stage_results or {})
                    if n == 7
                    else _term_preview(stage_results or {}) if n == 8 else None
                ),
                notes=[],
            )
        )
    title = run_meta.get("name") or _default_name(labels, run_meta.get("completed_at"))
    subtitle = " · ".join(x for x in (labels.get("plant"), labels.get("disease")) if x) or None
    footer = f"Generated by Herbaflow{(': ' + frontend_url) if frontend_url else ''}"
    return ReportModel(title, subtitle, list(_ABOUT), stages, list(_PROVENANCE), footer)
