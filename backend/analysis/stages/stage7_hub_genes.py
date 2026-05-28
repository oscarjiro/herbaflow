import statistics
import networkx as nx
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession


def compute_hub_genes(G: nx.Graph, top_n: int = 20, use_hub_bottleneck: bool = True) -> dict:
    if len(G.nodes) == 0:
        return {"ranked": [], "threshold_degree": 0, "threshold_betweenness": 0}

    # Degree centrality: Freeman 1979 normalized form C_D(v) = deg(v)/(n-1), range 0-1.
    # nx.degree_centrality() implements this directly. Do NOT use G.degree() (raw count).
    degree_centrality = nx.degree_centrality(G)

    if len(G.nodes) == 1:
        node = list(G.nodes)[0]
        ranked_list = [{"gene_symbol": node, "degree": 0.0, "betweenness": 0.0,
                        "closeness": 0.0, "eigenvector": 0.0,
                        "is_hub": False, "is_hub_bottleneck": False, "rank": 1}]
        return {
            "ranked": ranked_list,
            "threshold_degree": 0,
            "threshold_betweenness": 0,
        }

    betweenness = nx.betweenness_centrality(G, normalized=True)
    closeness = nx.closeness_centrality(G)
    try:
        eigenvector = nx.eigenvector_centrality(G, max_iter=1000, tol=1e-6)
    except nx.PowerIterationFailedConvergence:
        eigenvector = nx.degree_centrality(G)

    degree_values = list(degree_centrality.values())
    bet_values = list(betweenness.values())

    if len(degree_values) >= 2:
        deg_mean = statistics.mean(degree_values)
        deg_std = statistics.stdev(degree_values)
        hub_degree_threshold = deg_mean + deg_std

        bet_mean = statistics.mean(bet_values)
        bet_std = statistics.stdev(bet_values)
        hub_bet_threshold = bet_mean + bet_std
    else:
        hub_degree_threshold = 0
        hub_bet_threshold = 0

    ranked = []
    for node in G.nodes:
        deg = degree_centrality[node]  # normalized 0-1 (Freeman 1979)
        bet = betweenness[node]
        is_hub = deg > hub_degree_threshold
        is_hub_bottleneck = is_hub and bet >= hub_bet_threshold
        # Only include keys with non-None values so stage_results JSONB stays clean.
        # disease_association_score / compound_support_score / final_score are future
        # enrichment fields and must NOT appear as null keys in the stored dict.
        entry = {
            "gene_symbol": node,
            "degree": round(deg, 6),
            "betweenness": round(bet, 6),
            "closeness": round(closeness[node], 6),
            "eigenvector": round(eigenvector[node], 6),
            "is_hub": is_hub,
            "is_hub_bottleneck": is_hub_bottleneck,
        }
        ranked.append({k: v for k, v in entry.items() if v is not None})

    if use_hub_bottleneck:
        # Hub+bottleneck composite score: Jeong et al., Nature 411:41-42, 2001.
        # Identifies nodes with both high degree (connectivity) and high betweenness
        # (information flow). Score = 0.5 * norm_degree + 0.5 * norm_betweenness.
        max_deg = max((e["degree"] for e in ranked), default=1) or 1
        max_bet = max((e["betweenness"] for e in ranked), default=1) or 1
        for e in ranked:
            e["hub_score"] = round(
                0.5 * (e["degree"] / max_deg) +
                0.5 * (e["betweenness"] / max_bet),
                6,
            )
        ranked.sort(key=lambda x: x["hub_score"], reverse=True)
    else:
        ranked.sort(key=lambda x: x["degree"], reverse=True)

    ranked = ranked[:top_n]
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    return {
        "ranked": ranked,
        "threshold_degree": round(hub_degree_threshold, 2),
        "threshold_betweenness": round(hub_bet_threshold, 6) if isinstance(hub_bet_threshold, float) else 0,
    }


def compute_community_centrality(
    G: nx.Graph,
    gene_to_community: dict[str, int],
) -> dict[int, list[dict]]:
    """Compute centrality metrics within each Leiden community.

    For each community, extract the subgraph and compute:
    - degree_centrality (normalized 0-1 within community)
    - betweenness_centrality
    - closeness_centrality
    - eigenvector_centrality (fallback to degree if not convergent)

    Returns dict keyed by community_id → list of gene dicts ranked by
    community-local degree (descending).

    Communities with fewer than 2 nodes return an empty list — no
    meaningful centrality can be computed on isolated nodes.

    Scientific basis: Barabási et al. (2011) Nat Rev Genet 12(1):56–68.
    Hub genes within a community are more pharmacologically actionable
    than global hubs, which often reflect housekeeping proteins.
    """
    communities: dict[int, list] = {}
    for node in G.nodes:
        cid = gene_to_community.get(node)
        if cid is not None:
            communities.setdefault(cid, []).append(node)

    result = {}
    for cid, nodes in communities.items():
        if len(nodes) < 2:
            result[cid] = []
            continue

        subgraph = G.subgraph(nodes).copy()

        degree = nx.degree_centrality(subgraph)
        betweenness = nx.betweenness_centrality(subgraph, normalized=True)
        # For disconnected subgraphs, closeness_centrality returns 0.0 for unreachable nodes.
        # This is acceptable — isolated community members have no meaningful closeness.
        closeness = nx.closeness_centrality(subgraph)
        try:
            eigenvector = nx.eigenvector_centrality(subgraph, max_iter=500)
        except nx.PowerIterationFailedConvergence:
            eigenvector = nx.degree_centrality(subgraph)

        hub_list = sorted(
            [
                {
                    "gene_symbol": n,
                    "community_id": cid,
                    "community_degree": round(degree.get(n, 0), 6),
                    "community_betweenness": round(betweenness.get(n, 0), 6),
                    "community_closeness": round(closeness.get(n, 0), 6),
                    "community_eigenvector": round(eigenvector.get(n, 0), 6),
                    "community_size": len(nodes),
                }
                for n in nodes
            ],
            key=lambda x: x["community_degree"],
            reverse=True,
        )
        result[cid] = hub_list

    return result


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage6 = (run.stage_results or {}).get("stage_6", {})
    # Use raw_edges (flat dicts) if available; edges may be Cytoscape-wrapped {data:{...}}
    raw_edges = stage6.get("raw_edges") or stage6.get("edges", [])

    # Build gene→community lookup from Stage 6 node data
    gene_to_community: dict[str, int] = {}
    for node in stage6.get("nodes", []):
        node_data = node.get("data", {})
        gene = node_data.get("id", "")
        comm_id = node_data.get("community_id")
        if gene and comm_id is not None:
            gene_to_community[gene] = int(comm_id)

    G = nx.Graph()
    for edge in raw_edges:
        src = edge.get("source") or edge.get("data", {}).get("source", "")
        tgt = edge.get("target") or edge.get("data", {}).get("target", "")
        wt = edge.get("combined_score") or edge.get("data", {}).get("weight", 1.0)
        if src and tgt:
            G.add_edge(src, tgt, weight=wt)

    result = compute_hub_genes(
        G,
        top_n=config.hub_genes.top_n,
        use_hub_bottleneck=config.hub_genes.use_hub_bottleneck,
    )

    # Inject community_id into each hub gene entry
    for entry in result["ranked"]:
        entry["community_id"] = gene_to_community.get(entry["gene_symbol"], 0)

    # Per-community centrality: identify hub genes within each Leiden module
    result["community_hubs"] = compute_community_centrality(G, gene_to_community)

    # Write to target_rankings table
    from uuid import uuid4
    from datetime import datetime
    from app.models.analysis import TargetRanking
    from app.models.target import Target
    from sqlmodel import select

    for entry in result["ranked"]:
        gene = entry["gene_symbol"]
        target_result = await session.exec(select(Target).where(Target.gene_symbol == gene))
        target = target_result.first()
        if not target:
            continue
        ranking = TargetRanking(
            ranking_id=uuid4(),
            analysis_id=run.analysis_id,
            target_id=target.target_id,
            degree_centrality=float(entry["degree"]),
            betweenness_centrality=entry["betweenness"],
            closeness_centrality=entry["closeness"],
            eigenvector_centrality=entry["eigenvector"],
            rank_position=entry["rank"],
            created_at=datetime.utcnow(),
        )
        session.add(ranking)

    await session.commit()
    return result
