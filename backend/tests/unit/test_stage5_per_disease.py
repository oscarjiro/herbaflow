"""Unit tests for Stage 5 combined overlap stats."""
from unittest.mock import AsyncMock, MagicMock
from analysis.stages import stage5_overlap
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun


def make_run(stage3_genes: list[str], stage4_data: dict):
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {}
    run.stage_results = {
        "stage_3": {"target_gene_symbols": stage3_genes},
        "stage_4": stage4_data,
    }
    return run


async def test_combined_overlap_unchanged():
    """Combined overlap stats include all expected keys."""
    compound_genes = ["BRCA1", "EGFR", "AKT1"]
    disease_genes_flat = ["BRCA1", "EGFR", "TP53"]
    stage4_data = {
        "disease_gene_symbols": disease_genes_flat,
    }
    run = make_run(compound_genes, stage4_data)
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage5_overlap.run(run, config, session)

    # Combined overlap: BRCA1 and EGFR
    assert result["overlap_count"] == 2
    assert set(result["overlap"]) == {"BRCA1", "EGFR"}
    assert result["compound_only_count"] == 1   # AKT1
    assert result["disease_only_count"] == 1    # TP53
    assert "jaccard" in result
    assert "p_value" in result
    assert "significant" in result
    assert "venn" in result
    assert "per_disease" not in result
