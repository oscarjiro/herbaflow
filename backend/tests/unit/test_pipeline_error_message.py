import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import analysis.pipeline as pipeline
import pytest

ANALYSIS_ID = UUID("00000000-0000-0000-0000-000000000099")


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _factory():
    return _FakeSession()


@pytest.mark.asyncio
async def test_failed_stage_logs_traceback_but_stores_safe_message(caplog):
    fake_run = MagicMock()
    fake_run.status = "stage_3_running"
    fake_run.parameters = {}
    fake_run.mode = "auto"

    with patch.object(pipeline.analysis_repo, "get_run", AsyncMock(return_value=fake_run)), \
         patch.object(pipeline.analysis_repo, "update_run_status", AsyncMock()) as upd, \
         patch.object(pipeline.PipelineConfig, "from_dict", MagicMock(return_value=object())), \
         patch.dict(pipeline.STAGE_RUNNERS, {3: AsyncMock(side_effect=ValueError("boom secret /etc/passwd"))}):
        with caplog.at_level(logging.ERROR):
            await pipeline.run_stage(ANALYSIS_ID, 3, _factory)

    # The failed update carries a safe message
    failed_calls = [c for c in upd.call_args_list if c.kwargs.get("status") == "failed"]
    assert failed_calls, "expected a status=failed update"
    msg = failed_calls[-1].kwargs["error_message"]
    assert "Target identification" in msg and "stage 3" in msg
    for bad in ["Traceback", "ValueError", "/etc/passwd", ".py", "boom secret"]:
        assert bad not in msg

    # The full traceback IS in the server logs
    assert "Traceback" in caplog.text
    assert "ValueError" in caplog.text
