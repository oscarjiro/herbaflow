from unittest.mock import AsyncMock, MagicMock, patch
from analysis.stages import stage1_selection
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun


def make_run(plant_ids=None):
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {"_plant_ids": plant_ids or []}
    run.stage_results = {}
    return run


def make_fake_compound(compound_id: str):
    m = MagicMock()
    m.compound_id = compound_id
    return m


async def test_stage1_returns_compounds_for_plant_ids():
    run = make_run(plant_ids=["pl_1", "pl_2"])
    config = PipelineConfig()
    session = AsyncMock()
    fake_compounds = [make_fake_compound("c1"), make_fake_compound("c2"), make_fake_compound("c3")]

    with patch(
        "analysis.stages.stage1_selection.get_compounds_for_plants",
        return_value=fake_compounds,
    ) as mock_get:
        result = await stage1_selection.run(run, config, session)

    mock_get.assert_called_once_with(session, ["pl_1", "pl_2"])
    assert result["compound_count"] == 3
    assert result["compound_ids"] == ["c1", "c2", "c3"]
    assert result["plant_ids"] == ["pl_1", "pl_2"]


async def test_stage1_empty_plant_ids_returns_error():
    run = make_run(plant_ids=[])
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage1_selection.run(run, config, session)

    assert result["compound_count"] == 0
    assert result["compound_ids"] == []
    assert "error" in result


async def test_stage1_no_compounds_found():
    run = make_run(plant_ids=["pl_ghost"])
    config = PipelineConfig()
    session = AsyncMock()

    with patch(
        "analysis.stages.stage1_selection.get_compounds_for_plants",
        return_value=[],
    ):
        result = await stage1_selection.run(run, config, session)

    assert result["compound_count"] == 0
    assert result["compound_ids"] == []
