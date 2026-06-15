"""Stage-5..8 + C-T-P/PPI static chart renderers (matplotlib, headless Agg).

Pure: each function takes already-built data (stage_results slices or a results_handoff graph)
and returns PNG bytes, or None when the chart is not drawable (conditional-PNG rule).
No DB/async/API.
"""

from __future__ import annotations

import io
import math
from typing import Any

import matplotlib
import matplotlib.cm as cm
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
    colors = cm.autumn_r([v / (max(vals) or 1) for v in vals])
    fig, ax = plt.subplots(figsize=(6, max(2.0, 0.4 * len(ordered))))
    ax.barh(labels, vals, color=colors)
    ax.set_xlabel("hub-bottleneck composite score")
    ax.set_title(f"Top {len(ordered)} hub genes")
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

# Shared sequential colormap for "higher value = more important" scores (gene count,
# hub-bottleneck composite). enrichplot convention: the important (high) end is a dark,
# saturated red; the low end is faint. Never put the important value at the invisible
# yellow end. Reused by the enrichment dotplot, the hub bar, and the PPI node colouring.
SEQUENTIAL_CMAP = "Reds"

ENRICHMENT_FULL_NAME = {
    "GO:BP": "Biological Process",
    "GO:MF": "Molecular Function",
    "GO:CC": "Cellular Component",
    "KEGG": "KEGG pathways",
    "REAC": "Reactome pathways",
    "WP": "WikiPathways",
}


def enrichment_title(category: str) -> str:
    return f"Functional enrichment: {ENRICHMENT_FULL_NAME.get(category, category)}"


def category_slug(source: str) -> str:
    return _CATEGORY_SLUG.get(source, source.replace(":", "_"))


def render_enrichment_bubble(
    stage8: dict[str, Any], category: str, *, overlap_size: int | None
) -> bytes | None:
    terms = [t for t in stage8.get("terms", []) if t.get("source") == category and t.get("p_value")]
    if not terms or not overlap_size:
        return None
    total = len(terms)
    # Most significant first (smallest adjusted p), keep top 20.
    terms = sorted(terms, key=lambda t: t["p_value"])[:20]
    # Reverse for y-axis so the most significant term sits at the top.
    terms = list(reversed(terms))
    y = list(range(len(terms)))
    x = [-math.log10(max(t["p_value"], 1e-300)) for t in terms]
    counts = [len(t.get("intersection", [])) for t in terms]
    labels = [_trunc(t.get("name") or t["term_id"], 40) for t in terms]
    title = enrichment_title(category)
    if total > 20:
        title = f"{title} (top 20 of {total})"
    fig, ax = plt.subplots(figsize=(8, max(2.5, 0.45 * len(terms))))
    sc = ax.scatter(
        x,
        y,
        s=120,
        c=counts,
        cmap=SEQUENTIAL_CMAP,
        alpha=0.6,
        edgecolors="#333333",
        linewidths=0.5,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("−log₁₀(adjusted p)")
    ax.set_title(title)
    fig.colorbar(sc, ax=ax, label="gene count")
    return _png(fig)


_TYPE_COLOR = {"compound": "#4C9F70", "target": "#3066BE", "pathway": "#B5179E"}

_TYPE_STYLE: dict[str, tuple[str, str]] = {
    "compound": ("#2E8B57", "o"),
    "target": ("#3066BE", "o"),
    "pathway": ("#E07B39", "^"),
}


def _trunc(s: str, n: int = 22) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def render_ctp_network(graph: dict[str, Any]) -> bytes | None:
    """Concentric shell-layout C-T-P network (compounds centre → targets ring → pathways rim).
    Node size ∝ degree; colour+shape by type with a legend; labels truncated to 22 chars.
    Returns None when there are no edges (conditional-PNG rule)."""
    edges = graph.get("edges", [])
    if not edges:
        return None
    g: nx.Graph = nx.Graph()
    for n in graph.get("nodes", []):
        g.add_node(n["id"], **n)
    for e in edges:
        g.add_edge(e["source"], e["target"])
    shells = [
        [n["id"] for n in graph["nodes"] if n.get("type") == t]
        for t in ("compound", "target", "pathway")
    ]
    shells = [s for s in shells if s]
    pos = nx.shell_layout(g, nlist=shells)
    deg = dict(g.degree())
    fig, ax = plt.subplots(figsize=(11, 11))
    nx.draw_networkx_edges(g, pos, ax=ax, edge_color="#CCCCCC", width=0.8)
    for t, (color, marker) in _TYPE_STYLE.items():
        ids = [n for n in g.nodes if g.nodes[n].get("type") == t]
        if not ids:
            continue
        nx.draw_networkx_nodes(
            g,
            pos,
            nodelist=ids,
            ax=ax,
            node_color=color,
            node_shape=marker,
            node_size=[120 + 60 * deg.get(i, 0) for i in ids],
            label=t.capitalize(),
        )
    nx.draw_networkx_labels(
        g,
        pos,
        ax=ax,
        font_size=7,
        labels={n: _trunc(str(g.nodes[n].get("label") or n)) for n in g.nodes},
    )
    ax.legend(scatterpoints=1)
    ax.set_title("Compound–target–pathway network")
    ax.axis("off")
    return _png(fig)


def render_ppi_network(
    graph: dict[str, Any], *, hub_scores: dict[str, float], min_confidence: float
) -> bytes | None:
    """PPI network: connected nodes via kamada_kawai, isolated nodes in a bottom tray.
    Node size ∝ degree; node colour = hub composite score (red→yellow autumn_r colourbar);
    edge width ∝ confidence. Returns None when there are no nodes."""
    nodes = [n["id"] for n in graph.get("nodes", [])]
    if not nodes:
        return None
    g: nx.Graph = nx.Graph()
    g.add_nodes_from(nodes)
    for e in graph.get("edges", []):
        g.add_edge(e["source"], e["target"], confidence=e.get("confidence") or 0.4)
    connected = [n for n in nodes if g.degree(n) > 0]
    isolated = [n for n in nodes if g.degree(n) == 0]
    sub = g.subgraph(connected)
    pos: dict[str, tuple[float, float]] = nx.kamada_kawai_layout(sub) if connected else {}
    for i, n in enumerate(isolated):
        pos[n] = ((i - (len(isolated) - 1) / 2) * 0.25, -1.4)
    deg = dict(g.degree())
    fig, ax = plt.subplots(figsize=(9, 9))
    widths = [0.5 + 3 * (g[u][v].get("confidence") or 0.4) for u, v in g.edges()]
    nx.draw_networkx_edges(g, pos, ax=ax, edge_color="#BBBBBB", width=widths)
    sc = nx.draw_networkx_nodes(
        g,
        pos,
        ax=ax,
        nodelist=nodes,
        node_size=[150 + 80 * deg.get(n, 0) for n in nodes],
        node_color=[hub_scores.get(n, 0.0) for n in nodes],
        cmap="autumn_r",
    )
    nx.draw_networkx_labels(g, pos, ax=ax, font_size=7)
    if isolated:
        ax.text(
            0,
            -1.75,
            f"{len(isolated)} isolated — no STRING interactions at confidence ≥ {min_confidence}",
            ha="center",
            fontsize=8,
            color="#666666",
        )
    fig.colorbar(sc, ax=ax, label="hub composite score")
    ax.set_title("PPI network")
    ax.axis("off")
    return _png(fig)
