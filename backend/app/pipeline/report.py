"""Pure report model + markdown renderer (Software Lock §4.6a — no DB/async/API). The model is the
single home for the run's human-readable science; render_markdown emits the .md now, a PDF renderer
can consume the same model later."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app import contracts


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
        out.append(f"## Stage {st.n} — {st.name}")
        out += ["", st.finding, ""]
        if st.params:
            out += ["**Parameters**", ""]
            for p in st.params:
                val = f"{p.value} {p.unit}" if p.unit else p.value
                out.append(f"- **{p.label}:** {val} — {p.description}")
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
