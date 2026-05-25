"""Unit tests for Stage 5 per-disease overlap breakdown."""
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


async def test_per_disease_overlap_computed_correctly():
    """per_disease contains correct overlap counts for each disease."""
    compound_genes = ["BRCA1", "EGFR", "AKT1"]
    stage4_data = {
        "disease_gene_symbols": ["BRCA1", "EGFR", "TP53"],
        "disease_gene_symbols_by_disease": {
            "dis_1": ["BRCA1", "TP53"],   # overlap with compound: BRCA1
            "dis_2": ["EGFR", "TP53"],     # overlap with compound: EGFR
        },
    }
    run = make_run(compound_genes, stage4_data)
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage5_overlap.run(run, config, session)

    assert "per_disease" in result
    pd = result["per_disease"]

    assert "dis_1" in pd
    assert pd["dis_1"]["overlap_count"] == 1
    assert "BRCA1" in pd["dis_1"]["overlap"]

    assert "dis_2" in pd
    assert pd["dis_2"]["overlap_count"] == 1
    assert "EGFR" in pd["dis_2"]["overlap"]


async def test_combined_overlap_unchanged():
    """Combined overlap stats are identical to pre-per-disease output."""
    compound_genes = ["BRCA1", "EGFR", "AKT1"]
    disease_genes_flat = ["BRCA1", "EGFR", "TP53"]
    stage4_data = {
        "disease_gene_symbols": disease_genes_flat,
        "disease_gene_symbols_by_disease": {
            "dis_1": disease_genes_flat,
        },
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


async def test_per_disease_empty_when_no_disease_gene_map():
    """per_disease is empty dict when stage4 lacks disease_gene_symbols_by_disease."""
    run = make_run(
        ["BRCA1", "EGFR"],
        {
            "disease_gene_symbols": ["BRCA1"],
            # no disease_gene_symbols_by_disease key
        },
    )
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage5_overlap.run(run, config, session)

    assert result["per_disease"] == {}
    # Combined still works
    assert result["overlap_count"] == 1


async def test_per_disease_no_overlap():
    """per_disease correctly reports zero overlap when sets are disjoint."""
    run = make_run(
        ["AKT1", "MTOR"],
        {
            "disease_gene_symbols": ["TP53", "BRCA1"],
            "disease_gene_symbols_by_disease": {
                "dis_1": ["TP53", "BRCA1"],
            },
        },
    )
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage5_overlap.run(run, config, session)

    assert result["per_disease"]["dis_1"]["overlap_count"] == 0
    assert result["per_disease"]["dis_1"]["overlap"] == []
