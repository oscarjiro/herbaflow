from unittest.mock import AsyncMock, MagicMock, patch
from analysis.stages import stage4_disease_targets
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun


def make_run(disease_id=None):
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {"_disease_id": disease_id}
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


async def test_stage4_no_disease_returns_empty():
    run = make_run(disease_id=None)
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_id"] is None
    assert result["disease_name"] is None
    assert result["disease_target_count"] == 0
    assert result["targets"] == []
    assert result["disease_gene_symbols"] == []


async def test_stage4_uses_db_cache_and_emits_stage_level_disease():
    run = make_run(disease_id="dis_1")
    config = PipelineConfig()
    session = AsyncMock()

    fake_disease = make_fake_disease("dis_1", "Type 2 Diabetes")
    fake_target = make_fake_target("AKT1", "P31749")

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        return_value=fake_disease,
    ), patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_targets_for_disease",
        return_value=[(fake_target, 0.7)],
    ):
        result = await stage4_disease_targets.run(run, config, session)

    # Stage-level disease context (emitted once, not per row)
    assert result["disease_id"] == "dis_1"
    assert result["disease_name"] == "Type 2 Diabetes"
    # Lean target row — no per-row disease fields, no diseases[] list
    assert result["disease_target_count"] == 1
    row = result["targets"][0]
    assert row == {
        "gene_symbol": "AKT1",
        "uniprot_accession": "P31749",
        "score": 0.7,
        "source": "db_cache",
    }
    assert "diseases" not in row
    assert "disease_name" not in row


async def test_stage4_deduplicates_repeated_gene():
    run = make_run(disease_id="dis_1")
    config = PipelineConfig()
    session = AsyncMock()

    fake_disease = make_fake_disease("dis_1", "Diabetes")
    dup = make_fake_target("TP53")

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        return_value=fake_disease,
    ), patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_targets_for_disease",
        return_value=[(dup, 0.8), (dup, 0.6)],
    ):
        result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_target_count"] == 1
    assert result["disease_gene_symbols"] == ["TP53"]


async def test_stage4_unknown_disease_returns_empty_with_id():
    run = make_run(disease_id="dis_ghost")
    config = PipelineConfig()
    session = AsyncMock()

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        return_value=None,
    ):
        result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_id"] == "dis_ghost"
    assert result["disease_name"] is None
    assert result["disease_target_count"] == 0


async def test_stage4_manual_targets_mode():
    """manual_targets mode bypasses Open Targets; no disease context."""
    mock_run = MagicMock()
    mock_run.stage_results = {}
    mock_run.parameters = {
        "_disease_input_mode": "manual_targets",
        "_injected_disease_targets": ["TP53", "BRCA1", "PTEN"],
    }
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage4_disease_targets.run(mock_run, config, session)

    assert result["disease_id"] is None
    assert result["disease_name"] is None
    assert result["disease_target_count"] == 3
    genes = [t["gene_symbol"] for t in result["targets"]]
    assert {"TP53", "BRCA1", "PTEN"} <= set(genes)
    # lean rows
    assert "disease_name" not in result["targets"][0]


async def test_stage4_manual_targets_mode_empty_list():
    mock_run = MagicMock()
    mock_run.stage_results = {}
    mock_run.parameters = {
        "_disease_input_mode": "manual_targets",
        "_injected_disease_targets": [],
    }
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage4_disease_targets.run(mock_run, config, session)

    assert result["disease_target_count"] == 0
    assert result["targets"] == []


async def test_stage4_manual_targets_normalized():
    """Manual disease targets are canonicalized to HGNC and changes reported."""
    import app.services.gene_symbols as gs
    gs._MAP = {
        "TNFA": {"symbol": "TNF", "kind": "alias"},
        "TP53": {"symbol": "TP53", "kind": "approved"},
    }

    mock_run = MagicMock()
    mock_run.stage_results = {}
    mock_run.parameters = {
        "_disease_input_mode": "manual_targets",
        "_injected_disease_targets": ["TNFA", "TP53", "ZZZ9"],
    }
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage4_disease_targets.run(mock_run, config, session)

    symbols = result["disease_gene_symbols"]
    assert "TNF" in symbols
    assert "TP53" in symbols
    assert "TNFA" not in symbols
    assert {"from": "TNFA", "to": "TNF"} in result["normalization"]["changed"]
    assert "ZZZ9" in result["normalization"]["unrecognized"]
    assert "ZZZ9" in symbols
    gs._MAP = None


def test_open_targets_module_removed():
    """The dead live Open Targets fallback must be deleted entirely."""
    import importlib
    import pytest
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("integrations.open_targets")


async def test_stage4_empty_cache_returns_empty_targets():
    """When the disease exists but has no cached targets, return empty — no live fallback."""
    run = make_run(disease_id="dis_1")
    config = PipelineConfig()
    session = AsyncMock()

    fake_disease = make_fake_disease("dis_1", "Diabetes")
    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        return_value=fake_disease,
    ), patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_targets_for_disease",
        return_value=[],
    ):
        result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_id"] == "dis_1"
    assert result["disease_name"] == "Diabetes"
    assert result["disease_target_count"] == 0
    assert result["targets"] == []
    assert result["disease_gene_symbols"] == []
