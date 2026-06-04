from unittest.mock import AsyncMock, MagicMock

from analysis.models import PipelineConfig
from analysis.stages import stage5_overlap
from app.models.analysis import AnalysisRun


def make_run(compound_genes, disease_genes):
    run = MagicMock(spec=AnalysisRun)
    run.stage_results = {
        "stage_3": {"target_gene_symbols": list(compound_genes)},
        "stage_4": {"disease_gene_symbols": list(disease_genes)},
    }
    return run


async def test_stage5_returns_single_overlap_no_per_disease():
    run = make_run(["AKT1", "TP53", "EGFR"], ["TP53", "EGFR", "BRCA1"])
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage5_overlap.run(run, config, session)

    assert result["overlap_count"] == 2
    assert sorted(result["overlap"]) == ["EGFR", "TP53"]
    assert "jaccard" in result
    assert "p_value" in result
    # multi-disease breakdown is gone
    assert "per_disease" not in result


async def test_stage5_no_overlap():
    run = make_run(["AKT1"], ["TP53"])
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage5_overlap.run(run, config, session)

    assert result["overlap_count"] == 0
    assert result["significant"] is False
