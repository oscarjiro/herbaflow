import statistics
import networkx as nx
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession


def compute_hub_genes(G: nx.Graph, top_n: int = 20) -> dict:
    if len(G.nodes) == 0:
        return {"ranked": [], "hub_degree_threshold": 0, "hub_betweenness_threshold": 0}

    degrees = dict(G.degree())

    if len(G.nodes) == 1:
        node = list(G.nodes)[0]
        return {
            "ranked": [{"gene_symbol": node, "degree": 0, "betweenness": 0.0,
                        "closeness": 0.0, "eigenvector": 0.0,
                        "is_hub": False, "is_hub_bottleneck": False, "rank": 1}],
            "hub_degree_threshold": 0,
            "hub_betweenness_threshold": 0,
        }

    betweenness = nx.betweenness_centrality(G, normalized=True)
    closeness = nx.closeness_centrality(G)
    try:
        eigenvector = nx.eigenvector_centrality(G, max_iter=1000, tol=1e-6)
    except nx.PowerIterationFailedConvergence:
        eigenvector = {n: 0.0 for n in G.nodes}

    degree_values = list(degrees.values())
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
        deg = degrees[node]
        bet = betweenness[node]
        is_hub = deg > hub_degree_threshold
        is_hub_bottleneck = is_hub and bet >= hub_bet_threshold
        # Only include keys with non-None values so stage_results JSONB stays clean.
        # disease_association_score / compound_support_score / final_score are future
        # enrichment fields and must NOT appear as null keys in the stored dict.
        entry = {
            "gene_symbol": node,
            "degree": deg,
            "betweenness": round(bet, 6),
            "closeness": round(closeness[node], 6),
            "eigenvector": round(eigenvector[node], 6),
            "is_hub": is_hub,
            "is_hub_bottleneck": is_hub_bottleneck,
        }
        ranked.append({k: v for k, v in entry.items() if v is not None})

    ranked.sort(key=lambda x: x["degree"], reverse=True)
    ranked = ranked[:top_n]
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    return {
        "ranked": ranked,
        "hub_degree_threshold": round(hub_degree_threshold, 2),
        "hub_betweenness_threshold": round(hub_bet_threshold, 6) if isinstance(hub_bet_threshold, float) else 0,
    }


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage6 = (run.stage_results or {}).get("stage_6", {})
    edges = stage6.get("edges", [])

    G = nx.Graph()
    for edge in edges:
        G.add_edge(edge["source"], edge["target"], weight=edge.get("combined_score", 1.0))

    result = compute_hub_genes(G, top_n=config.hub_genes.top_n)

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
