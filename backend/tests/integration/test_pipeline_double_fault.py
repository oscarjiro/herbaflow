import pytest
from unittest.mock import patch
from app.database import async_session_factory
from app.repositories import analysis_repo
from analysis import pipeline

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_record_failure_swallows_db_write_error(created_runs):
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(
            s, name="t", mode="auto",
            parameters={"_input_mode": "manual_targets", "_disease_input_mode": "manual_targets",
                        "_injected_disease_targets": ["TP53"]},
        )
    created_runs.append(run.analysis_id)

    async def stage_boom(*a, **k):
        raise ValueError("stage error")

    # Allow the first update_run_status call (stage_4_running) to succeed,
    # then raise on every subsequent call to simulate a DB outage that hits
    # only the failure-recording write inside _record_failure.
    _real_update = analysis_repo.update_run_status
    call_count = {"n": 0}

    async def write_boom_after_first(*a, **k):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return await _real_update(*a, **k)
        raise RuntimeError("DB down during failure recording")

    # Stage fails, AND the failure-recording write also fails: must not raise.
    with patch.dict(pipeline.STAGE_RUNNERS, {4: stage_boom}), \
         patch.object(analysis_repo, "update_run_status", write_boom_after_first):
        # Should complete without raising despite the double fault.
        await pipeline.run_stage(run.analysis_id, 4, async_session_factory)
