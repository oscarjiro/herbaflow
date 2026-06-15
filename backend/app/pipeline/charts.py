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
import networkx as nx

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib_venn import venn2  # noqa: E402


def _png(fig: Any) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def venn_title(plant_label: str | None, disease_label: str | None) -> str:
    """Generate a title for the venn diagram with optional plant and disease labels."""
    if plant_label and disease_label:
        return f"{plant_label} and {disease_label} target overlap"
    return "Target overlap"


def render_venn(
    stage5: dict[str, Any], *, plant_label: str | None = None, disease_label: str | None = None
) -> bytes | None:
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
    ax.set_title(venn_title(plant_label, disease_label))
    return _png(fig)


def hub_bar_colors(vals: list[float]) -> Any:
    """Map MCC scores to the shared sequential palette (dark = high)."""
    cmap = matplotlib.colormaps[SEQUENTIAL_CMAP]
    hi = max(vals) or 1
    return cmap([v / hi for v in vals])


def render_hub_bar(stage7: dict[str, Any]) -> bytes | None:
    hubs = stage7.get("hubs", [])
    if not hubs:
        return None
    ordered = sorted(hubs, key=lambda h: h.get("mcc") or 0.0)  # ascending -> top at the top
    labels = [h.get("gene_symbol") or str(h.get("target_id")) for h in ordered]
    vals = [h.get("mcc") or 0.0 for h in ordered]
    colors = hub_bar_colors(vals)
    fig, ax = plt.subplots(figsize=(6, max(2.0, 0.4 * len(ordered))))
    ax.barh(labels, vals, color=colors)
    ax.set_xlabel("MCC score")
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
# MCC score). enrichplot convention: the important (high) end is a dark,
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


# Above this many nodes the full tripartite graph is an unreadable hairball, so the figure
# shows the highest-degree core (the full graph stays in the Cytoscape CSV bundle). Readability
# heuristic, not a publication standard; tune in the live proof.
CTP_FULL_RENDER_MAX = 80

_TYPE_COLOR = {"compound": "#4C9F70", "target": "#3066BE", "pathway": "#B5179E"}

_TYPE_STYLE: dict[str, tuple[str, str]] = {
    "compound": ("#2E8B57", "o"),
    "target": ("#3066BE", "o"),
    "pathway": ("#E07B39", "^"),
}


def _trunc(s: str, n: int = 22) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def select_ctp_core(graph: dict[str, Any], cap: int = CTP_FULL_RENDER_MAX) -> list[str]:
    """Node ids to draw.

    If total nodes <= cap, return all. Otherwise return the highest-degree core, keeping type
    balance: allocate the cap across the present node types proportionally to each type's node
    count (floor 1 per present type), and within each type keep the highest-degree nodes. So no
    whole type (compound/target/pathway) vanishes from the figure.
    """
    nodes = graph.get("nodes", [])
    total = len(nodes)
    if total <= cap:
        return [n["id"] for n in nodes]

    # Build a temporary graph to compute degree for each node id.
    g: nx.Graph = nx.Graph()
    for node in nodes:
        g.add_node(node["id"])
    for e in graph.get("edges", []):
        g.add_edge(e["source"], e["target"])
    degree = dict(g.degree())

    # Group ids by type.
    by_type: dict[str, list[str]] = {}
    for node in nodes:
        t = node.get("type", "")
        by_type.setdefault(t, []).append(node["id"])

    present_types = [t for t in by_type if by_type[t]]
    n_types = len(present_types)

    kept: list[str] = []
    for t in present_types:
        type_ids = by_type[t]
        # Proportional allocation, floor 1.
        keep_t = max(1, round(cap * len(type_ids) / total))
        # Sort descending by degree, take top keep_t.
        sorted_ids = sorted(type_ids, key=lambda nid: degree.get(nid, 0), reverse=True)
        kept.extend(sorted_ids[:keep_t])

    # Rounding may push us slightly over or under; trim excess evenly if over.
    # (Under is fine — we never drop below floor-1 per type.)
    if len(kept) > cap + n_types:
        kept = kept[: cap + n_types]

    return kept


def render_ctp_network(graph: dict[str, Any]) -> bytes | None:
    """Concentric shell-layout C-T-P network (compounds centre -> targets ring -> pathways rim).

    Node size proportional to degree; colour+shape by type with a legend; labels truncated to 22
    chars. Returns None when there are no edges (conditional-PNG rule). When the graph exceeds
    CTP_FULL_RENDER_MAX nodes, draws only the highest-degree core (induced subgraph) to keep the
    figure legible; the title notes how many nodes are shown vs. the total.
    """
    edges = graph.get("edges", [])
    if not edges:
        return None

    all_nodes = graph.get("nodes", [])
    total_nodes = len(all_nodes)

    keep = set(select_ctp_core(graph))
    k = len(keep)

    # Induced subgraph: only nodes in keep + edges where BOTH endpoints are in keep.
    g: nx.Graph = nx.Graph()
    for node in all_nodes:
        if node["id"] in keep:
            g.add_node(node["id"], **node)
    for e in edges:
        if e["source"] in keep and e["target"] in keep:
            g.add_edge(e["source"], e["target"])

    shells = [
        [node["id"] for node in all_nodes if node.get("type") == t and node["id"] in keep]
        for t in ("compound", "target", "pathway")
    ]
    shells = [s for s in shells if s]
    pos = nx.shell_layout(g, nlist=shells)
    deg = dict(g.degree())

    fig, ax = plt.subplots(figsize=(11, 11))
    nx.draw_networkx_edges(g, pos, ax=ax, edge_color="#CCCCCC", width=0.8)
    for t, (color, marker) in _TYPE_STYLE.items():
        ids = [nid for nid in g.nodes if g.nodes[nid].get("type") == t]
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
        labels={nid: _trunc(str(g.nodes[nid].get("label") or nid)) for nid in g.nodes},
    )
    ax.legend(scatterpoints=1, bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0.0)
    if total_nodes > k:
        title = f"Compound-target-pathway network (top {k} of {total_nodes} nodes shown)"
    else:
        title = "Compound-target-pathway network"
    ax.set_title(title)
    ax.axis("off")
    return _png(fig)


# Above this many nodes the PPI fallback figure becomes a hairball; draw the top-scored core
# instead. The full graph data is still exported in the Cytoscape CSV bundle.
PPI_FULL_RENDER_MAX = 80


def select_ppi_core(
    graph: dict[str, Any],
    hub_scores: dict[str, float],
    cap: int = PPI_FULL_RENDER_MAX,
) -> list[str]:
    """Node ids to draw.

    If total nodes <= cap, return all. Otherwise return the cap highest-ranked nodes by hub
    MCC score (fallback to 0.0 for unscored), tie-broken deterministically by id.
    """
    nodes = graph.get("nodes", [])
    if len(nodes) <= cap:
        return [n["id"] for n in nodes]
    sorted_ids = sorted(
        (n["id"] for n in nodes),
        key=lambda nid: (-hub_scores.get(nid, 0.0), nid),
    )
    return sorted_ids[:cap]


def render_ppi_network(
    graph: dict[str, Any], *, hub_scores: dict[str, float], min_confidence: float
) -> bytes | None:
    """PPI network: connected nodes via kamada_kawai, isolated nodes in a bottom tray.

    Node size proportional to degree; node colour = hub MCC score via the shared
    sequential palette (dark = high); edge width proportional to confidence. Returns None
    when there are no nodes. When the graph exceeds PPI_FULL_RENDER_MAX nodes, draws only
    the top-scored core (induced subgraph); the title notes the truncation.
    """
    all_nodes = [n["id"] for n in graph.get("nodes", [])]
    if not all_nodes:
        return None

    total_m = len(all_nodes)
    keep = set(select_ppi_core(graph, hub_scores))
    k = len(keep)

    # Restrict to the kept induced subgraph.
    nodes = [n for n in all_nodes if n in keep]
    g: nx.Graph = nx.Graph()
    g.add_nodes_from(nodes)
    for e in graph.get("edges", []):
        if e["source"] in keep and e["target"] in keep:
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
        cmap=SEQUENTIAL_CMAP,
    )
    nx.draw_networkx_labels(g, pos, ax=ax, font_size=7)
    if isolated:
        ax.text(
            0,
            -1.75,
            f"{len(isolated)} isolated: no interactions at confidence >= {min_confidence}",
            ha="center",
            fontsize=8,
            color="#666666",
        )
    fig.colorbar(sc, ax=ax, label="hub MCC score")
    if k < total_m:
        ax.set_title(f"Protein-protein interaction network (top {k} of {total_m} nodes shown)")
    else:
        ax.set_title("Protein-protein interaction network")
    ax.axis("off")
    return _png(fig)
