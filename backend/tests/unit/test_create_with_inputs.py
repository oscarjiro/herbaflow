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


# ---------------------------------------------------------------------------
# Test: inject_compounds_service stamps stage_1 as user_provided + inputs;
#       the synthetic stage_2 must NOT be written.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_compounds_stamps_user_provided_and_drops_stage2():
    """stage_1 gains state='user_provided' + inputs.rejected; stage_2 is never written."""
    from unittest.mock import MagicMock, patch
    from app.services.manual_inputs import inject_compounds_service

    run = MagicMock()
    run.analysis_id = uuid.uuid4()
    run.status = "pending"
    run.stage_results = {}
    run.parameters = {}

    # One validated compound, one failed raw string
    validated_compound = {
        "compound_id": str(uuid.uuid4()),
        "canonical_name": "Ethanol",
        "canonical_key": "pubchem:702",
        "pubchem_cid": 702,
        "adme_pass": True,
        "is_np_exception": False,
        "is_pains_positive": False,
        "molecular_weight": 46.07,
        "logp": -0.14,
        "tpsa": 20.23,
        "hbond_donors": 1,
        "hbond_acceptors": 1,
        "np_likeness_score": -1.0,
        "rotatable_bonds": 0,
    }
    failed_input = "BADINPUT"

    written_stage_results: dict = {}

    async def fake_update(session, analysis_id, status, **kwargs):
        if "stage_results" in kwargs:
            written_stage_results.update(kwargs["stage_results"])

    mock_session = MagicMock()

    with patch("app.services.manual_inputs.validate_compounds_batch",
               new=AsyncMock(return_value=([validated_compound], [failed_input]))), \
         patch("app.services.manual_inputs.deduplicate_compounds",
               new=AsyncMock(return_value=(["ETHANOL", failed_input], []))), \
         patch("app.services.manual_inputs.analysis_repo.update_run_status",
               new=AsyncMock(side_effect=fake_update)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters",
               new=AsyncMock()), \
         patch("app.services.compound_persist.persist_validated_compounds",
               new=AsyncMock(return_value=0)):

        await inject_compounds_service(
            compounds=["ETHANOL", failed_input],
            run=run,
            session=mock_session,
        )

    stage1 = written_stage_results.get("stage_1", {})

    assert stage1["state"] == "user_provided"
    assert stage1["inputs"]["rejected"] == ["BADINPUT"]
    assert "stage_2" not in written_stage_results  # synthetic stage_2 dropped
