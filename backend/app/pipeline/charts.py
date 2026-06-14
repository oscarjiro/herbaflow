"""Stage-5..8 + C-T-P/PPI static chart renderers (matplotlib, headless Agg).

Pure: each function takes already-built data (stage_results slices or a results_handoff graph)
and returns PNG bytes, or None when the chart is not drawable (conditional-PNG rule).
No DB/async/API.
"""

from __future__ import annotations

import io
from typing import Any

import matplotlib
import networkx as nx

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib_venn import venn2  # noqa: E402


def _png(fig: Any) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def render_venn(stage5: dict[str, Any]) -> bytes | None:
    count = stage5.get("count")
    a = stage5.get("compound_target_count")
    b = stage5.get("disease_target_count")
    if count is None or a is None or b is None:
        return None
    only_a, only_b = max(a - count, 0), max(b - count, 0)
    if only_a + only_b + count == 0:
        return None
    fig, ax = plt.subplots(figsize=(6, 5))
    venn2(
        subsets=(only_a, only_b, count), set_labels=("Compound targets", "Disease targets"), ax=ax
    )
    ax.set_title("Stage 5 — target overlap")
    return _png(fig)


def render_hub_bar(stage7: dict[str, Any]) -> bytes | None:
    hubs = stage7.get("hubs", [])
    if not hubs:
        return None
    ordered = sorted(hubs, key=lambda h: h.get("composite") or 0.0)  # ascending -> top at the top
    labels = [h.get("gene_symbol") or str(h.get("target_id")) for h in ordered]
    vals = [h.get("composite") or 0.0 for h in ordered]
    fig, ax = plt.subplots(figsize=(6, max(2.0, 0.4 * len(ordered))))
    ax.barh(labels, vals)
    ax.set_xlabel("Hub-bottleneck composite score")
    ax.set_title("Stage 7 — top hub genes")
    return _png(fig)


ENRICHMENT_CATEGORIES = ["GO:BP", "GO:MF", "GO:CC", "KEGG", "REAC", "WP"]
_CATEGORY_SLUG = {
    "GO:BP": "BP",
    "GO:MF": "MF",
    "GO:CC": "CC",
    "KEGG": "KEGG",
    "REAC": "REAC",
    "WP": "WP",
}


def category_slug(source: str) -> str:
    return _CATEGORY_SLUG.get(source, source.replace(":", "_"))


def render_enrichment_bubble(
    stage8: dict[str, Any], category: str, *, overlap_size: int | None
) -> bytes | None:
    terms = [t for t in stage8.get("terms", []) if t.get("source") == category and t.get("p_value")]
    if not terms or not overlap_size:
        return None
    terms = sorted(terms, key=lambda t: len(t.get("intersection", [])) / overlap_size)[-20:]
    y = list(range(len(terms)))
    counts = [len(t.get("intersection", [])) for t in terms]
    ratio = [c / overlap_size for c in counts]
    padj = [t["p_value"] for t in terms]
    fig, ax = plt.subplots(figsize=(7, max(2.5, 0.45 * len(terms))))
    sc = ax.scatter(ratio, y, s=[max(c, 1) * 40 for c in counts], c=padj, cmap="autumn", norm=None)
    ax.set_yticks(y)
    ax.set_yticklabels([t.get("name") or t["term_id"] for t in terms])
    ax.set_xlabel("gene ratio")
    ax.set_title(f"Stage 8 — enrichment ({category_slug(category)})")
    cb = fig.colorbar(sc, ax=ax, label="adjusted p-value")
    cb.ax.invert_yaxis()
    for c in sorted(set(counts))[:3]:
        ax.scatter([], [], s=max(c, 1) * 40, c="grey", label=str(c))
    ax.legend(title="gene count", loc="lower right", labelspacing=1)
    return _png(fig)


_TYPE_COLOR = {"compound": "#4C9F70", "target": "#3066BE", "pathway": "#B5179E"}


def render_network(graph: dict[str, list[dict[str, Any]]], *, title: str) -> bytes | None:
    edges = graph.get("edges", [])
    if not edges:
        return None
    g = nx.Graph()
    for n in graph.get("nodes", []):
        g.add_node(n["id"], **n)
    for e in edges:
        g.add_edge(e["source"], e["target"])
    pos = nx.spring_layout(g, seed=42)
    colors = []
    for _id, data in g.nodes(data=True):
        if data.get("type") in _TYPE_COLOR:
            colors.append(_TYPE_COLOR[data["type"]])
        else:
            colors.append("#E63946" if data.get("is_hub") == "true" else "#3066BE")
    fig, ax = plt.subplots(figsize=(8, 8))
    nx.draw_networkx(
        g,
        pos,
        ax=ax,
        node_color=colors,
        node_size=200,
        font_size=7,
        edge_color="#BBBBBB",
        with_labels=True,
    )
    ax.set_title(title)
    ax.axis("off")
    return _png(fig)
