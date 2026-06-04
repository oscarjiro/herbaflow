import asyncio
import pytest
from datetime import datetime, timedelta
from app.database import async_session_factory
from app.repositories import analysis_repo
from app import main

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_reaper_loop_sweeps_once(created_runs, monkeypatch):
    monkeypatch.setattr(main, "REAPER_INTERVAL_SECONDS", 0.2)
    monkeypatch.setattr(main, "STALE_THRESHOLD_SECONDS", 1)

    # Create and advance run to an in-progress state
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(s, name="t", mode="auto", parameters={})

    async with async_session_factory() as s:
        await analysis_repo.update_run_status(
            s, run.analysis_id, status="stage_2_running", current_stage=2
        )

    # Back-date updated_at so the reaper sees it as stale (600s >> 1s threshold)
    async with async_session_factory() as s:
        frozen = await analysis_repo.get_run(s, run.analysis_id)
        frozen.updated_at = datetime.utcnow() - timedelta(seconds=600)
        s.add(frozen)
        await s.commit()

    created_runs.append(run.analysis_id)

    # Start the reaper loop; allow 2 s for the 0.2 s sleep + live DB round-trip (~0.8 s)
    task = asyncio.create_task(main._reaper_loop())
    await asyncio.sleep(2.0)
    task.cancel()

    async with async_session_factory() as s:
        got = await analysis_repo.get_run(s, run.analysis_id)
    assert got.status == "failed"
