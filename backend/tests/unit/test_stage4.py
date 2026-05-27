from unittest.mock import AsyncMock, MagicMock, patch
from analysis.stages import stage4_disease_targets
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun


def make_run(disease_ids=None):
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {"_disease_ids": disease_ids or []}
    run.stage_results = {}
    return run


def make_fake_disease(disease_id: str, disease_name: str, ontology_id: str = "EFO_0000400"):
    m = MagicMock()
    m.disease_id = disease_id
    m.disease_name = disease_name
    m.ontology_id = ontology_id
    return m


def make_fake_target(gene_symbol: str, uniprot: str = "P00000"):
    m = MagicMock()
    m.gene_symbol = gene_symbol
    m.uniprot_accession = uniprot
    return m


async def test_stage4_no_disease_ids_returns_empty():
    run = make_run(disease_ids=[])
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_target_count"] == 0
    assert result["targets"] == []
    assert result["disease_gene_symbols"] == []


async def test_stage4_uses_db_cache():
    run = make_run(disease_ids=["dis_1"])
    config = PipelineConfig()
    session = AsyncMock()

    fake_disease = make_fake_disease("dis_1", "Type 2 Diabetes")
    fake_target = make_fake_target("AKT1", "P31749")

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        return_value=fake_disease,
    ):
        with patch(
            "analysis.stages.stage4_disease_targets.disease_repo.get_targets_for_disease",
            return_value=[(fake_target, 0.7)],
        ):
            result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_target_count"] == 1
    assert result["targets"][0]["gene_symbol"] == "AKT1"
    assert result["targets"][0]["source"] == "db_cache"
    assert result["targets"][0]["association_score"] == 0.7


async def test_stage4_deduplicates_gene_across_diseases():
    run = make_run(disease_ids=["dis_1", "dis_2"])
    config = PipelineConfig()
    session = AsyncMock()

    fake_disease1 = make_fake_disease("dis_1", "Diabetes")
    fake_disease2 = make_fake_disease("dis_2", "Obesity")
    shared_target = make_fake_target("TP53")

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        side_effect=[fake_disease1, fake_disease2],
    ):
        with patch(
            "analysis.stages.stage4_disease_targets.disease_repo.get_targets_for_disease",
            side_effect=[[(shared_target, 0.8)], [(shared_target, 0.6)]],
        ):
            result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_target_count"] == 1
    assert "TP53" in result["disease_gene_symbols"]


async def test_stage4_skips_unknown_disease():
    run = make_run(disease_ids=["dis_ghost"])
    config = PipelineConfig()
    session = AsyncMock()

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        return_value=None,
    ):
        result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_target_count"] == 0


async def test_stage4_manual_targets_mode():
    """When _disease_input_mode is manual_targets, stage4 uses injected_disease_targets."""
    mock_run = MagicMock()
    mock_run.stage_results = {
        "stage_3": {
            "target_gene_symbols": ["TP53", "EGFR"],
        }
    }
    mock_run.parameters = {
        "_disease_input_mode": "manual_targets",
        "_injected_disease_targets": ["TP53", "BRCA1", "PTEN"],
    }
    mock_config = PipelineConfig()
    mock_session = AsyncMock()

    result = await stage4_disease_targets.run(mock_run, mock_config, mock_session)

    assert result["disease_target_count"] == 3
    gene_symbols = [t["gene_symbol"] for t in result["targets"]]
    assert "TP53" in gene_symbols
    assert "BRCA1" in gene_symbols


async def test_stage4_manual_targets_mode_empty_list():
    """When _disease_input_mode is manual_targets with empty list, returns empty result."""
    mock_run = MagicMock()
    mock_run.stage_results = {}
    mock_run.parameters = {
        "_disease_input_mode": "manual_targets",
        "_injected_disease_targets": [],
    }
    mock_config = PipelineConfig()
    mock_session = AsyncMock()

    result = await stage4_disease_targets.run(mock_run, mock_config, mock_session)

    assert result["disease_target_count"] == 0
    assert result["targets"] == []
