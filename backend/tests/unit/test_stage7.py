from unittest.mock import AsyncMock, MagicMock
from analysis.stages import stage7_hub_genes
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun


async def test_stage7_ignores_isolated_overlap_nodes():
    """Stage 6 may now emit isolated nodes; Stage 7 hub ranking (edge-derived) must ignore them."""
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {}
    run.stage_results = {
        "stage_6": {
            "nodes": [
                {"data": {"id": "AKT1", "community_id": 0}},
                {"data": {"id": "TNF", "community_id": 0}},
                {"data": {"id": "MDM2", "community_id": 0}},
                {"data": {"id": "LONELY", "community_id": 1}},
            ],
            "raw_edges": [
                {"source": "AKT1", "target": "TNF", "combined_score": 0.7},
                {"source": "TNF", "target": "MDM2", "combined_score": 0.6},
            ],
        }
    }
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage7_hub_genes.run(run, config, session)

    ranked_ids = {r["gene_symbol"] for r in result["ranked"]}
    assert "LONELY" not in ranked_ids
    assert ranked_ids == {"AKT1", "TNF", "MDM2"}
