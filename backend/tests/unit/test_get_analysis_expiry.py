"""Regression: GET /analyses/{id} 500'd on completed runs because expires_at (read back
from a timestamptz column as timezone-AWARE) was compared against a naive datetime.utcnow().
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from app.models.analysis import AnalysisRun


def _run(expires_at):
    return AnalysisRun(
        analysis_name="t", status="complete", mode="auto",
        current_stage=8, stage_results={}, parameters={},
        created_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
        expires_at=expires_at, updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_get_analysis_handles_timezone_aware_expires_at():
    """A tz-aware future expires_at must not raise TypeError; the run is returned."""
    from app.routers import analyses
    run = _run(datetime.now(timezone.utc) + timedelta(hours=24))
    with patch.object(analyses.analysis_repo, "get_run", new=AsyncMock(return_value=run)), \
            patch.object(analyses.analysis_repo, "mark_failed_if_stale", new=AsyncMock(return_value=run)):
        resp = await analyses.get_analysis(run.analysis_id, session=AsyncMock())
    assert resp.status == "complete"


@pytest.mark.asyncio
async def test_get_analysis_410_when_expired_with_aware_timestamp():
    """A tz-aware past expires_at is correctly detected as expired (410), not a 500."""
    from app.routers import analyses
    from fastapi import HTTPException
    run = _run(datetime.now(timezone.utc) - timedelta(hours=1))
    with patch.object(analyses.analysis_repo, "get_run", new=AsyncMock(return_value=run)), \
            patch.object(analyses.analysis_repo, "mark_failed_if_stale", new=AsyncMock(return_value=run)):
        with pytest.raises(HTTPException) as ei:
            await analyses.get_analysis(run.analysis_id, session=AsyncMock())
    assert ei.value.status_code == 410
