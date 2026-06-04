from unittest.mock import patch

import pytest
from analysis import pipeline
from app.database import async_session_factory
from app.repositories import analysis_repo
from integrations._retry import ServiceUnavailableError

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_provider_outage_records_provider_unavailable_kind(created_runs):
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(
            s, name="t", mode="auto",
            parameters={"_input_mode": "manual_targets", "_disease_input_mode": "manual_targets",
                        "_injected_disease_targets": ["TP53"]},
        )
    created_runs.append(run.analysis_id)

    async def boom(*a, **k):
        raise ServiceUnavailableError("STRING-DB", 503)

    with patch.dict(pipeline.STAGE_RUNNERS, {4: boom}):
        await pipeline.run_stage(run.analysis_id, 4, async_session_factory)

    async with async_session_factory() as s:
        got = await analysis_repo.get_run(s, run.analysis_id)
    assert got.status == "failed"
    assert got.stage_results.get("_run_health", {}).get("failure_kind") == "provider_unavailable"
    assert "try again" in (got.error_message or "").lower()


async def test_internal_error_records_internal_kind(created_runs):
    async with async_session_factory() as s:
        run = await analysis_repo.create_run(
            s, name="t", mode="auto",
            parameters={"_input_mode": "manual_targets", "_disease_input_mode": "manual_targets",
                        "_injected_disease_targets": ["TP53"]},
        )
    created_runs.append(run.analysis_id)

    async def boom(*a, **k):
        raise ValueError("bug")

    with patch.dict(pipeline.STAGE_RUNNERS, {4: boom}):
        await pipeline.run_stage(run.analysis_id, 4, async_session_factory)

    async with async_session_factory() as s:
        got = await analysis_repo.get_run(s, run.analysis_id)
    assert got.status == "failed"
    assert got.stage_results.get("_run_health", {}).get("failure_kind") == "internal_error"
