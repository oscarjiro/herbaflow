from datetime import datetime, timedelta

import pytest
from app.database import async_session_factory
from app.repositories import analysis_repo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_touch_heartbeat_advances_updated_at(created_runs):
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(s, name="t", mode="auto", parameters={})
        # Force updated_at into the past.
        run.updated_at = datetime.utcnow() - timedelta(minutes=10)
        s.add(run)
        await s.commit()
    created_runs.append(run.analysis_id)

    async with async_session_factory() as s:
        await analysis_repo.touch_heartbeat(s, run.analysis_id)

    async with async_session_factory() as s:
        got = await analysis_repo.get_run(s, run.analysis_id)
    assert (datetime.utcnow() - got.updated_at.replace(tzinfo=None)) < timedelta(minutes=1)
