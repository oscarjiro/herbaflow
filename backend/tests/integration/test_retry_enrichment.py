import pytest
from unittest.mock import AsyncMock, patch
from app.database import async_session_factory
from app.repositories import analysis_repo
from app.routers import analyses

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_degraded_run():
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(s, name="t", mode="auto", parameters={})
        warning = {"provider": "g:Profiler", "reason": "down"}
        await analysis_repo.update_run_status(
            s, run.analysis_id, status="complete", completed=True,
            stage_results={
                "stage_7": {"ranked": [{"gene_symbol": "TP53", "community_id": 0}]},
                "stage_8": {"degraded": True, "warning": warning, "total_significant": 0},
            },
        )
    return run.analysis_id


async def test_retry_enrichment_accepts_degraded_run(client, created_runs):
    aid = await _make_degraded_run()
    created_runs.append(aid)
    # Mock the background task so no real stage-8 (live g:Profiler) run fires during the test.
    with patch.object(analyses, "run_stage", new=AsyncMock()):
        resp = await client.post(f"/analyses/{aid}/retry-enrichment")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stage_8_running"


async def test_retry_enrichment_rejects_non_degraded_run(client, created_runs):
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(s, name="t", mode="auto", parameters={})
        await analysis_repo.update_run_status(
            s, run.analysis_id, status="complete", completed=True,
            stage_results={"stage_8": {"total_significant": 5}},
        )
    created_runs.append(run.analysis_id)
    resp = await client.post(f"/analyses/{run.analysis_id}/retry-enrichment")
    assert resp.status_code == 400
