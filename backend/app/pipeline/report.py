"""Pure report model + markdown renderer (Software Lock §4.6a — no DB/async/API). The model is the
single home for the run's human-readable science; render_markdown emits the .md now, a PDF renderer
can consume the same model later."""

from __future__ import annotations

from dataclasses import dataclass, field


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
