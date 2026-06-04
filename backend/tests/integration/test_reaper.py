import pytest
from datetime import datetime, timedelta
from app.database import async_session_factory
from app.repositories import analysis_repo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_reap_stale_runs_marks_frozen_running_run_failed(created_runs):
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(s, name="t", mode="auto", parameters={})
        await analysis_repo.update_run_status(s, run.analysis_id, status="stage_3_running", current_stage=3)
        # Freeze updated_at well past the threshold.
        frozen = await analysis_repo.get_run(s, run.analysis_id)
        frozen.updated_at = datetime.utcnow() - timedelta(seconds=600)
        s.add(frozen)
        await s.commit()
    created_runs.append(run.analysis_id)

    async with async_session_factory() as s:
        reaped = await analysis_repo.reap_stale_runs(s, threshold_seconds=120)
    assert reaped >= 1

    async with async_session_factory() as s:
        got = await analysis_repo.get_run(s, run.analysis_id)
    assert got.status == "failed"
    assert got.stage_results.get("_run_health", {}).get("failure_kind") == "timeout"


async def test_reap_leaves_fresh_running_run_alone(created_runs):
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(s, name="t", mode="auto", parameters={})
        await analysis_repo.update_run_status(s, run.analysis_id, status="stage_3_running", current_stage=3)
    created_runs.append(run.analysis_id)

    async with async_session_factory() as s:
        await analysis_repo.reap_stale_runs(s, threshold_seconds=120)
    async with async_session_factory() as s:
        got = await analysis_repo.get_run(s, run.analysis_id)
    assert got.status == "stage_3_running"
