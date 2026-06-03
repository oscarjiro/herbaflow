# backend/tests/unit/test_create_with_inputs.py
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from app.schemas.analysis import CreateAnalysisRequest, InjectCompoundsResponse


def _fake_run():
    run = AsyncMock()
    run.analysis_id = uuid.uuid4()
    run.status = "pending"
    run.mode = "guided"
    run.current_stage = None
    run.created_at = None
    run.updated_at = None
    return run


@pytest.mark.asyncio
async def test_create_injects_before_scheduling_pipeline():
    """Compounds are injected synchronously; the pipeline is scheduled only after."""
    order: list[str] = []

    async def fake_inject(compounds, run, session):
        order.append("inject")
        return InjectCompoundsResponse(
            injected=len(compounds), failed=[], duplicates_removed=0,
            duplicate_names=[], cached=0,
        )

    class FakeBG:
        def add_task(self, *a, **k):
            order.append("schedule")

    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(return_value=_fake_run())), \
         patch("app.services.manual_inputs.inject_compounds_service", new=AsyncMock(side_effect=fake_inject)):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": [], "disease_id": "d1",
             "compounds": ["CCO"], "parameters": {}})
        await analyses.create_analysis(body, FakeBG(), session=AsyncMock())

    assert order == ["inject", "schedule"]


@pytest.mark.asyncio
async def test_standard_mode_schedules_without_inject():
    scheduled = []

    class FakeBG:
        def add_task(self, *a, **k): scheduled.append(a)

    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(return_value=_fake_run())):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": ["p1"], "disease_id": "d1",
             "parameters": {}})
        await analyses.create_analysis(body, FakeBG(), session=AsyncMock())

    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_manual_disease_targets_persisted_into_stored_parameters():
    """Server derives _disease_input_mode + _injected_disease_targets into stored params."""
    captured = {}

    async def capture_create(session, name, mode, parameters, disease_id=None):
        captured["parameters"] = parameters
        captured["disease_id"] = disease_id
        return _fake_run()

    class FakeBG:
        def add_task(self, *a, **k): pass

    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(side_effect=capture_create)):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": ["p1"], "disease_id": None,
             "manual_disease_targets": ["TP53", "EGFR"], "parameters": {}})
        await analyses.create_analysis(body, FakeBG(), session=AsyncMock())

    p = captured["parameters"]
    assert p["_disease_input_mode"] == "manual_targets"
    assert p["_injected_disease_targets"] == ["TP53", "EGFR"]


@pytest.mark.asyncio
async def test_all_invalid_compounds_deletes_run_and_422_no_schedule():
    """All-invalid manual input -> 422, the created run is deleted, pipeline NOT scheduled."""
    from fastapi import HTTPException
    scheduled = []
    deleted = []

    async def fake_inject(compounds, run, session):
        return InjectCompoundsResponse(
            injected=0, failed=list(compounds), duplicates_removed=0,
            duplicate_names=[], cached=0,
        )

    class FakeBG:
        def add_task(self, *a, **k): scheduled.append(a)

    run = _fake_run()
    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(return_value=run)), \
         patch.object(analyses.analysis_repo, "delete_run", new=AsyncMock(side_effect=lambda s, aid: deleted.append(aid))), \
         patch("app.services.manual_inputs.inject_compounds_service", new=AsyncMock(side_effect=fake_inject)):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": [], "disease_id": "d1",
             "compounds": ["bad"], "parameters": {}})
        with pytest.raises(HTTPException) as ei:
            await analyses.create_analysis(body, FakeBG(), session=AsyncMock())
    assert ei.value.status_code == 422
    assert deleted == [run.analysis_id]
    assert scheduled == []
