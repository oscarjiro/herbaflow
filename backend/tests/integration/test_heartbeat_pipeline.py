import asyncio
import pytest
from datetime import datetime, timedelta
from app.database import async_session_factory
from app.repositories import analysis_repo
from analysis import pipeline

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_heartbeat_advances_updated_at_during_slow_stage(created_runs, monkeypatch):
    monkeypatch.setattr(pipeline, "HEARTBEAT_INTERVAL_SECONDS", 0.2)
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(
            s, name="t", mode="guided",
            parameters={"_input_mode": "manual_targets", "_disease_input_mode": "manual_targets",
                        "_injected_disease_targets": ["TP53"]},
        )
        # Force updated_at into the past so any heartbeat advance is detectable.
        run.updated_at = datetime.utcnow() - timedelta(seconds=300)
        s.add(run)
        await s.commit()
    created_runs.append(run.analysis_id)

    async def slow_stage(*a, **k):
        await asyncio.sleep(0.7)  # longer than several heartbeat intervals
        return {"disease_target_count": 1, "targets": []}

    monkeypatch.setitem(pipeline.STAGE_RUNNERS, 4, slow_stage)
    start = datetime.utcnow() - timedelta(seconds=1)
    await pipeline.run_stage(run.analysis_id, 4, async_session_factory)

    async with async_session_factory() as s:
        got = await analysis_repo.get_run(s, run.analysis_id)
    # updated_at was refreshed by a heartbeat partway through the slow stage.
    assert got.updated_at.replace(tzinfo=None) > start
