from collections import Counter

import igraph as ig
import leidenalg
import networkx as nx
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from integrations.stringdb import get_ppi_network


def detect_communities(
    G: nx.Graph,
    resolution: float = 1.0,
    seed: int = 42,
) -> dict[str, int]:
    """Run Leiden community detection on a NetworkX graph.

    Returns: dict mapping node_id → community_id (0-indexed int).
    Uses RBConfigurationVertexPartition with fixed seed for reproducibility.

    Optimisation passes: leidenalg's default ``n_iterations=2`` is used (the
    parameter is intentionally left unset). Each iteration is one full local-move /
    aggregate sweep; two passes are the package default and are sufficient for the
    small PPI graphs handled here (tens–low hundreds of nodes), which converge well
    before extra sweeps would change the partition. A negative ``n_iterations`` would
    instead iterate to convergence — not needed at this scale, and a fixed count plus
    the fixed ``seed`` keeps results deterministic across runs.
    Refs: Traag, Waltman & van Eck 2019, Sci. Rep. 9:5233 (Leiden algorithm);
    leidenalg.find_partition documentation.
    """
    if G.number_of_nodes() == 0:
        return {}
    if G.number_of_nodes() == 1:
        return {list(G.nodes())[0]: 0}

    # Convert NetworkX → igraph (preserving node order for mapping)
    node_list = list(G.nodes())
    node_index = {node: i for i, node in enumerate(node_list)}
    edges = [(node_index[u], node_index[v]) for u, v in G.edges()]

    ig_graph = ig.Graph(n=len(node_list), edges=edges)
    partition = leidenalg.find_partition(
        ig_graph,
        leidenalg.RBConfigurationVertexPartition,
        resolution_parameter=resolution,
        seed=seed,
    )
    return {node_list[i]: partition.membership[i] for i in range(len(node_list))}


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage5 = (run.stage_results or {}).get("stage_5", {})
    overlapping_genes = stage5.get("overlap", [])

    if not overlapping_genes:
        return {"node_count": 0, "edge_count": 0, "nodes": [], "edges": [], "n_communities": 0}

    edges = await get_ppi_network(
        overlapping_genes, min_confidence=config.ppi.min_confidence
    )

    overlap_set = set(g.upper() for g in overlapping_genes)
    all_genes: set[str] = set()
    for e in edges:
        all_genes.add(e.gene_a)
        all_genes.add(e.gene_b)

    # STRING returns edges, not a node list — overlap genes with no surviving interaction
    # would otherwise be silently dropped from the network, node_count, and every
    # downstream stage. Seed them so the node set represents every overlap gene; isolated
    # ones become degree-0 nodes (degree_map defaults to 0 for them below).
    all_genes |= overlap_set

    # Compute node degree for tooltip
    degree_map: dict[str, int] = {}
    raw_edges = []
    for e in edges:
        degree_map[e.gene_a] = degree_map.get(e.gene_a, 0) + 1
        degree_map[e.gene_b] = degree_map.get(e.gene_b, 0) + 1
        raw_edges.append({
            "source": e.gene_a,
            "target": e.gene_b,
            "combined_score": e.combined_score,
        })

    # Build NetworkX graph for community detection
    G = nx.Graph()
    for edge in raw_edges:
        G.add_edge(edge["source"], edge["target"])

    # Community detection on the connected graph only. Isolated overlap genes are NOT
    # added to G, so Leiden's partition of the connected component is byte-for-byte
    # unchanged; they receive their own singleton ids next.
    community_resolution = config.ppi.community_resolution
    community_map = detect_communities(G, resolution=community_resolution, seed=42)

    # Each isolated overlap gene (no STRING edge) belongs to no module → give it its own
    # singleton community id, continuing after the max connected id.
    isolated_genes = sorted(overlap_set - set(community_map.keys()))
    next_community_id = (max(community_map.values()) + 1) if community_map else 0
    for gene in isolated_genes:
        community_map[gene] = next_community_id
        next_community_id += 1

    # Cytoscape element format: {data: {...}}
    nodes = [
        {
            "data": {
                "id": g,
                "label": g,
                "type": "overlap" if g in overlap_set else "other",
                "degree": degree_map.get(g, 0),
                "community_id": community_map.get(g, 0),
            }
        }
        for g in sorted(all_genes)
    ]
    edge_list = [
        {
            "data": {
                "source": e["source"],
                "target": e["target"],
                "weight": e["combined_score"],
            }
        }
        for e in raw_edges
    ]

    # Count only real modules (>=2 members); singleton (isolated) communities are excluded
    # so the headline metric reflects actual biology, not trivial one-gene clusters.
    community_sizes = Counter(community_map.values())
    n_communities = sum(1 for size in community_sizes.values() if size >= 2)

    return {
        "node_count": len(nodes),
        "edge_count": len(edge_list),
        "nodes": nodes,
        "edges": edge_list,
        "min_confidence": config.ppi.min_confidence,
        "n_communities": n_communities,
        # raw_edges preserved for Stage 7 (NetworkX needs flat dicts)
        "raw_edges": raw_edges,
    }
