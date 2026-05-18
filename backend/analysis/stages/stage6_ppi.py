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

    all_genes = set()
    edge_list = []
    for e in edges:
        all_genes.add(e.gene_a)
        all_genes.add(e.gene_b)
        edge_list.append({
            "source": e.gene_a,
            "target": e.gene_b,
            "combined_score": e.combined_score,
            "experimental_score": e.experimental_score,
        })

    nodes = [{"id": g, "label": g} for g in sorted(all_genes)]

    return {
        "node_count": len(nodes),
        "edge_count": len(edge_list),
        "nodes": nodes,
        "edges": edge_list,
        "cytoscape": {
            "elements": {
                "nodes": [{"data": n} for n in nodes],
                "edges": [
                    {"data": {"source": e["source"], "target": e["target"], "weight": e["combined_score"]}}
                    for e in edge_list
                ],
            }
        },
    }
