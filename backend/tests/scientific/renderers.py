"""Server-side artifact renderers for the golden-dataset suite. Matplotlib Agg backend
(no display). Each function returns the written file path; tolerant of empty inputs."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402


def render_ppi(stage6: dict, out_dir: str, filename: str = "ppi_network.png") -> str:
    edges = stage6.get("raw_edges", [])
    G = nx.Graph()
    for e in edges:
        G.add_edge(e["source"], e["target"], weight=e.get("combined_score", 0.0))
    fig, ax = plt.subplots(figsize=(10, 8))
    if G.number_of_nodes() == 0:
        ax.text(0.5, 0.5, "No PPI edges", ha="center", va="center")
        ax.axis("off")
    else:
        pos = nx.spring_layout(G, seed=42)
        deg = dict(G.degree())
        nx.draw_networkx_nodes(G, pos, ax=ax,
                               node_size=[120 + 40 * deg[n] for n in G.nodes()],
                               node_color="#4C9F70")
        nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.3)
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=7)
        ax.axis("off")
    path = os.path.join(out_dir, filename)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def render_centrality(stage7: dict, out_dir: str, filename: str = "centrality.png", top_n: int = 20) -> str:
    ranked = stage7.get("ranked", [])[:top_n]
    genes = [r["gene_symbol"] for r in ranked]
    scores = [r.get("composite_score", r.get("degree_centrality", 0.0)) for r in ranked]
    fig, ax = plt.subplots(figsize=(8, max(3, 0.3 * len(genes) + 1)))
    if genes:
        ax.barh(genes[::-1], scores[::-1], color="#3A6EA5")
        ax.set_xlabel("centrality score")
    else:
        ax.text(0.5, 0.5, "No hub genes", ha="center", va="center")
        ax.axis("off")
    path = os.path.join(out_dir, filename)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def render_enrichment(stage8: dict, out_dir: str, filename: str = "enrichment.png", top_n: int = 15) -> str:
    terms = stage8.get("kegg", [])[:top_n]
    names = [t.get("term_name", t.get("term_id", "?")) for t in terms]
    neglog = [-(__import__("math").log10(max(t.get("fdr", 1.0), 1e-300))) for t in terms]
    fig, ax = plt.subplots(figsize=(8, max(3, 0.3 * len(names) + 1)))
    if names:
        ax.barh(names[::-1], neglog[::-1], color="#B5651D")
        ax.set_xlabel("-log10(FDR)")
    else:
        ax.text(0.5, 0.5, "No enriched KEGG terms", ha="center", va="center")
        ax.axis("off")
    path = os.path.join(out_dir, filename)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path
