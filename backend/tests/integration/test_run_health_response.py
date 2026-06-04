import pytest
from app.database import async_session_factory
from app.repositories import analysis_repo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_get_analysis_includes_derived_health_fields(client, created_runs):
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(
            s, name="t", mode="auto",
            parameters={"_input_mode": "manual_targets"},
        )
        await analysis_repo.update_run_status(
            s, run.analysis_id, status="complete",
            stage_results={"stage_3": {"target_count": 0},
                           "stage_8": {"degraded": True, "warning": {"provider": "g:Profiler", "reason": "down"}}},
            completed=True,
        )
    created_runs.append(run.analysis_id)

    resp = await client.get(f"/analyses/{run.analysis_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert body["has_results"] is False
    assert body["retriable"] is False
    assert body["warnings"] == [{"stage": 8, "provider": "g:Profiler", "reason": "down"}]
