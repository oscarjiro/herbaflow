import statistics
import networkx as nx
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession


def compute_hub_genes(G: nx.Graph, top_n: int = 20) -> dict:
    if len(G.nodes) == 0:
        return {"hub_genes": [], "threshold_degree": 0, "hub_betweenness_threshold": 0}

    degrees = dict(G.degree())

    if len(G.nodes) == 1:
        node = list(G.nodes)[0]
        hub_genes_list = [{"gene_symbol": node, "degree": 0, "betweenness_centrality": 0.0,
                            "closeness_centrality": 0.0, "eigenvector_centrality": 0.0,
                            "is_hub": False, "is_bottleneck": False, "rank": 1}]
        return {
            "hub_genes": hub_genes_list,
            "threshold_degree": 0,
            "hub_betweenness_threshold": 0, "threshold_betweenness": 0,
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

    hub_genes = []
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
            "betweenness_centrality": round(bet, 6),
            "closeness_centrality": round(closeness[node], 6),
            "eigenvector_centrality": round(eigenvector[node], 6),
            "is_hub": is_hub,
            "is_bottleneck": is_hub_bottleneck,
        }
        hub_genes.append({k: v for k, v in entry.items() if v is not None})

    hub_genes.sort(key=lambda x: x["degree"], reverse=True)
    hub_genes = hub_genes[:top_n]
    for i, r in enumerate(hub_genes):
        r["rank"] = i + 1

    return {
        "hub_genes": hub_genes,
        "threshold_degree": round(hub_degree_threshold, 2),
        "hub_betweenness_threshold": round(hub_bet_threshold, 6) if isinstance(hub_bet_threshold, float) else 0,
        "threshold_betweenness": round(hub_bet_threshold, 6) if isinstance(hub_bet_threshold, float) else 0,
    }


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage6 = (run.stage_results or {}).get("stage_6", {})
    # Use raw_edges (flat dicts) if available; edges may be Cytoscape-wrapped {data:{...}}
    raw_edges = stage6.get("raw_edges") or stage6.get("edges", [])

    G = nx.Graph()
    for edge in raw_edges:
        src = edge.get("source") or edge.get("data", {}).get("source", "")
        tgt = edge.get("target") or edge.get("data", {}).get("target", "")
        wt = edge.get("combined_score") or edge.get("data", {}).get("weight", 1.0)
        if src and tgt:
            G.add_edge(src, tgt, weight=wt)

    result = compute_hub_genes(G, top_n=config.hub_genes.top_n)

    # Write to target_rankings table
    from uuid import uuid4
    from datetime import datetime
    from app.models.analysis import TargetRanking
    from app.models.target import Target
    from sqlmodel import select

    for entry in result["hub_genes"]:
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
            betweenness_centrality=entry["betweenness_centrality"],
            closeness_centrality=entry["closeness_centrality"],
            eigenvector_centrality=entry["eigenvector_centrality"],
            rank_position=entry["rank"],
            created_at=datetime.utcnow(),
        )
        session.add(ranking)

    await session.commit()
    return result
