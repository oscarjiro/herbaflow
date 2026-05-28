"""Unit tests for analysis/pipeline.py — run_stage status transitions.

Tests the state machine behavior of run_stage:
- Skips when analysis status is already "failed"
- Updates status to stage_N_running before calling stage function
- Updates status to stage_N_complete after stage succeeds
- Updates status to "failed" when stage function raises
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import UUID

from analysis.pipeline import run_stage

ANALYSIS_ID = UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(status: str = "pending", mode: str = "auto", parameters: dict | None = None):
    run = MagicMock()
    run.analysis_id = ANALYSIS_ID
    run.status = status
    run.mode = mode
    run.parameters = parameters or {}
    run.stage_results = {}
    return run


def _make_session_factory(run_sequence: list):
    """Return a session_factory yielding a mock session.

    run_sequence: list of AnalysisRun mocks returned by analysis_repo.get_run
                  on successive calls.
    """
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=ctx)
    return factory


# ---------------------------------------------------------------------------
# test_run_stage_skips_when_status_is_failed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_stage_skips_when_status_is_failed():
    """If run.status == 'failed', run_stage returns immediately without touching stage_fn."""
    failed_run = _make_run(status="failed")
    factory = _make_session_factory([failed_run])

    fake_stage_fn = AsyncMock(return_value={"result": "data"})
    update_mock = AsyncMock()

    with patch("analysis.pipeline.analysis_repo.get_run", return_value=failed_run), \
         patch("analysis.pipeline.analysis_repo.update_run_status", update_mock), \
         patch("analysis.pipeline.STAGE_RUNNERS", {1: fake_stage_fn}):
        await run_stage(ANALYSIS_ID, 1, factory)

    fake_stage_fn.assert_not_called()
    update_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_stage_skips_when_run_is_none():
    """If get_run returns None (analysis not found), run_stage exits without error."""
    factory = _make_session_factory([])

    fake_stage_fn = AsyncMock(return_value={})
    update_mock = AsyncMock()

    with patch("analysis.pipeline.analysis_repo.get_run", return_value=None), \
         patch("analysis.pipeline.analysis_repo.update_run_status", update_mock), \
         patch("analysis.pipeline.STAGE_RUNNERS", {1: fake_stage_fn}):
        await run_stage(ANALYSIS_ID, 1, factory)

    fake_stage_fn.assert_not_called()
    update_mock.assert_not_called()


# ---------------------------------------------------------------------------
# test_run_stage_updates_status_to_running
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_stage_updates_status_to_running():
    """Before calling stage_fn, status is set to stage_N_running."""
    pending_run = _make_run(status="pending", mode="auto")
    factory = _make_session_factory([pending_run])

    stage_result = {"data": "ok"}
    fake_stage_fn = AsyncMock(return_value=stage_result)

    update_calls = []

    async def capture_update(session, analysis_id, status, **kwargs):
        update_calls.append(status)

    with patch("analysis.pipeline.analysis_repo.get_run", return_value=pending_run), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               side_effect=capture_update), \
         patch("analysis.pipeline.STAGE_RUNNERS", {3: fake_stage_fn}), \
         patch("analysis.pipeline.PipelineConfig") as mock_config_cls:
        mock_config_cls.from_dict.return_value = MagicMock()
        await run_stage(ANALYSIS_ID, 3, factory)

    # First update must be "running"
    assert update_calls[0] == "stage_3_running"


# ---------------------------------------------------------------------------
# test_run_stage_updates_status_to_complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_stage_updates_status_to_complete_in_auto_mode():
    """After stage_fn succeeds in auto mode, status becomes stage_N_complete."""
    run = _make_run(status="pending", mode="auto")
    factory = _make_session_factory([run])

    stage_result = {"targets": ["AKT1"]}
    fake_stage_fn = AsyncMock(return_value=stage_result)

    update_calls = []

    async def capture_update(session, analysis_id, status, **kwargs):
        update_calls.append(status)

    with patch("analysis.pipeline.analysis_repo.get_run", return_value=run), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               side_effect=capture_update), \
         patch("analysis.pipeline.STAGE_RUNNERS", {3: fake_stage_fn}), \
         patch("analysis.pipeline.asyncio.create_task"), \
         patch("analysis.pipeline.PipelineConfig") as mock_config_cls:
        mock_config_cls.from_dict.return_value = MagicMock()
        await run_stage(ANALYSIS_ID, 3, factory)

    # Second update must be "complete" (stage_3_complete in auto mode)
    assert "stage_3_complete" in update_calls


@pytest.mark.asyncio
async def test_run_stage_stage_8_updates_status_to_complete():
    """Stage 8 (last stage) updates status to 'complete' (not stage_8_complete)."""
    run = _make_run(status="pending", mode="auto")
    factory = _make_session_factory([run])

    stage_result = {"pathways": []}
    fake_stage_fn = AsyncMock(return_value=stage_result)

    update_calls = []
    update_kwargs_list = []

    async def capture_update(session, analysis_id, status, **kwargs):
        update_calls.append(status)
        update_kwargs_list.append(kwargs)

    with patch("analysis.pipeline.analysis_repo.get_run", return_value=run), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               side_effect=capture_update), \
         patch("analysis.pipeline.STAGE_RUNNERS", {8: fake_stage_fn}), \
         patch("analysis.pipeline.PipelineConfig") as mock_config_cls:
        mock_config_cls.from_dict.return_value = MagicMock()
        await run_stage(ANALYSIS_ID, 8, factory)

    # Stage 8 final status must be "complete"
    assert "complete" in update_calls
    # completed=True must be passed
    complete_idx = update_calls.index("complete")
    assert update_kwargs_list[complete_idx].get("completed") is True


@pytest.mark.asyncio
async def test_run_stage_guided_mode_sets_awaiting_approval():
    """In guided mode, after stage success status becomes stage_N_awaiting_approval."""
    run = _make_run(status="pending", mode="guided")
    factory = _make_session_factory([run])

    stage_result = {"compounds": []}
    fake_stage_fn = AsyncMock(return_value=stage_result)

    update_calls = []

    async def capture_update(session, analysis_id, status, **kwargs):
        update_calls.append(status)

    with patch("analysis.pipeline.analysis_repo.get_run", return_value=run), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               side_effect=capture_update), \
         patch("analysis.pipeline.STAGE_RUNNERS", {2: fake_stage_fn}), \
         patch("analysis.pipeline.PipelineConfig") as mock_config_cls:
        mock_config_cls.from_dict.return_value = MagicMock()
        await run_stage(ANALYSIS_ID, 2, factory)

    assert "stage_2_awaiting_approval" in update_calls


# ---------------------------------------------------------------------------
# test_run_stage_handles_stage_exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_stage_handles_stage_exception_sets_failed():
    """If stage_fn raises an exception, status is updated to 'failed'."""
    run = _make_run(status="pending", mode="auto")
    factory = _make_session_factory([run])

    fake_stage_fn = AsyncMock(side_effect=RuntimeError("ChEMBL timeout"))

    update_calls = []

    async def capture_update(session, analysis_id, status, **kwargs):
        update_calls.append(status)

    with patch("analysis.pipeline.analysis_repo.get_run", return_value=run), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               side_effect=capture_update), \
         patch("analysis.pipeline.STAGE_RUNNERS", {3: fake_stage_fn}), \
         patch("analysis.pipeline.PipelineConfig") as mock_config_cls:
        mock_config_cls.from_dict.return_value = MagicMock()
        await run_stage(ANALYSIS_ID, 3, factory)

    # Status must end in "failed"
    assert "failed" in update_calls


@pytest.mark.asyncio
async def test_run_stage_exception_error_message_contains_stage_number():
    """The error_message passed on failure includes the stage number."""
    run = _make_run(status="pending", mode="auto")
    factory = _make_session_factory([run])

    fake_stage_fn = AsyncMock(side_effect=ValueError("bad data"))

    captured_kwargs = {}

    async def capture_update(session, analysis_id, status, **kwargs):
        if status == "failed":
            captured_kwargs.update(kwargs)

    with patch("analysis.pipeline.analysis_repo.get_run", return_value=run), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               side_effect=capture_update), \
         patch("analysis.pipeline.STAGE_RUNNERS", {5: fake_stage_fn}), \
         patch("analysis.pipeline.PipelineConfig") as mock_config_cls:
        mock_config_cls.from_dict.return_value = MagicMock()
        await run_stage(ANALYSIS_ID, 5, factory)

    error_msg = captured_kwargs.get("error_message", "")
    assert "5" in error_msg, f"Stage number '5' not found in error_message: {error_msg!r}"
