from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from integrations.stringdb import get_ppi_network


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage5 = (run.stage_results or {}).get("stage_5", {})
    overlapping_genes = stage5.get("overlap", [])

    if not overlapping_genes:
        return {"node_count": 0, "edge_count": 0, "nodes": [], "edges": []}

    edges = await get_ppi_network(
        overlapping_genes, min_confidence=config.ppi.min_confidence
    )

    overlap_set = set(g.upper() for g in overlapping_genes)
    all_genes: set[str] = set()
    for e in edges:
        all_genes.add(e.gene_a)
        all_genes.add(e.gene_b)

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

    # Cytoscape element format: {data: {...}}
    nodes = [
        {
            "data": {
                "id": g,
                "label": g,
                "type": "overlap" if g in overlap_set else "other",
                "degree": degree_map.get(g, 0),
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

    return {
        "node_count": len(nodes),
        "edge_count": len(edge_list),
        "nodes": nodes,
        "edges": edge_list,
        "min_confidence": config.ppi.min_confidence,
        # raw_edges preserved for Stage 7 (NetworkX needs flat dicts)
        "raw_edges": raw_edges,
    }
