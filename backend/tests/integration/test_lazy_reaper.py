import pytest
from datetime import datetime, timedelta
from app.database import async_session_factory
from app.repositories import analysis_repo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_get_analysis_marks_stale_running_run_failed_inline(client, created_runs):
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(s, name="t", mode="auto", parameters={})
        await analysis_repo.update_run_status(s, run.analysis_id, status="stage_5_running", current_stage=5)
        frozen = await analysis_repo.get_run(s, run.analysis_id)
        frozen.updated_at = datetime.utcnow() - timedelta(seconds=600)
        s.add(frozen)
        await s.commit()
    created_runs.append(run.analysis_id)

    resp = await client.get(f"/analyses/{run.analysis_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["retriable"] is True  # timeout kind is retriable
