"""Unit tests for pipeline skip logic (T4.5).

Tests that start_pipeline() reads _input_mode from run.parameters and:
- skips the appropriate stages (writing sentinel dicts to stage_results)
- calls run_stage() at the correct first real stage number
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import UUID

ANALYSIS_ID = UUID("00000000-0000-0000-0000-000000000099")


def _make_run(input_mode: str | None = None, extra_params: dict | None = None):
    run = MagicMock()
    run.analysis_id = ANALYSIS_ID
    params = dict(extra_params or {})
    if input_mode is not None:
        params["_input_mode"] = input_mode
    run.parameters = params
    run.stage_results = {}
    run.status = "pending"
    return run


def _make_session_factory(run):
    """Return a session_factory whose async-context-manager yields a mock session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=ctx)
    return factory, session


# ---------------------------------------------------------------------------
# Test 1: standard mode (no _input_mode key) → runs stage 1, no skips
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_standard_mode_starts_at_stage_1():
    """Missing _input_mode defaults to standard — run_stage called with stage 1."""
    run = _make_run(input_mode=None)
    factory, session = _make_session_factory(run)

    captured_stage_results = {}

    async def fake_update_run_status(session, analysis_id, status, **kwargs):
        sr = kwargs.get("stage_results")
        if sr:
            captured_stage_results.update(sr)
        mock_run = MagicMock()
        mock_run.status = status
        return mock_run

    with patch("analysis.pipeline.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               new=AsyncMock(side_effect=fake_update_run_status)), \
         patch("analysis.pipeline.run_stage", new=AsyncMock()) as mock_run_stage:
        from analysis.pipeline import start_pipeline
        await start_pipeline(ANALYSIS_ID, ["pl_1"], ["d_1"], factory)

    # run_stage must be called with stage_num=1
    mock_run_stage.assert_called_once_with(ANALYSIS_ID, 1, factory)

    # No skipped stages written to stage_results
    for key, entry in captured_stage_results.items():
        assert entry.get("status") != "skipped", \
            f"standard mode must not write any skipped stage, but {key} has status='skipped'"


# ---------------------------------------------------------------------------
# Test 2: manual_compounds → stages 1–2 skipped, run_stage called with 3
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_compounds_skips_stages_1_2():
    """input_mode=manual_compounds: stages 1 and 2 are skipped, stage 3 runs."""
    run = _make_run(input_mode="manual_compounds")
    factory, session = _make_session_factory(run)

    captured_stage_results = {}

    async def fake_update_run_status(session, analysis_id, status, **kwargs):
        sr = kwargs.get("stage_results")
        if sr:
            captured_stage_results.update(sr)
        mock_run = MagicMock()
        mock_run.status = status
        return mock_run

    with patch("analysis.pipeline.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               new=AsyncMock(side_effect=fake_update_run_status)), \
         patch("analysis.pipeline.run_stage", new=AsyncMock()) as mock_run_stage:
        from analysis.pipeline import start_pipeline
        await start_pipeline(ANALYSIS_ID, ["pl_1"], ["d_1"], factory)

    # run_stage must be called with stage_num=3
    mock_run_stage.assert_called_once_with(ANALYSIS_ID, 3, factory)

    # stages 1 and 2 must be in stage_results with status="skipped"
    assert "stage_1" in captured_stage_results, "stage_1 missing from stage_results"
    assert "stage_2" in captured_stage_results, "stage_2 missing from stage_results"
    assert captured_stage_results["stage_1"]["status"] == "skipped"
    assert captured_stage_results["stage_2"]["status"] == "skipped"

    # stage_3 must NOT be in stage_results (it was run, not skipped)
    assert "stage_3" not in captured_stage_results


# ---------------------------------------------------------------------------
# Test 3: manual_targets → stages 1–3 skipped, run_stage called with 4
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_targets_skips_stages_1_2_3():
    """input_mode=manual_targets: stages 1, 2, and 3 are skipped, stage 4 runs."""
    run = _make_run(input_mode="manual_targets")
    factory, session = _make_session_factory(run)

    captured_stage_results = {}

    async def fake_update_run_status(session, analysis_id, status, **kwargs):
        sr = kwargs.get("stage_results")
        if sr:
            captured_stage_results.update(sr)
        mock_run = MagicMock()
        mock_run.status = status
        return mock_run

    with patch("analysis.pipeline.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               new=AsyncMock(side_effect=fake_update_run_status)), \
         patch("analysis.pipeline.run_stage", new=AsyncMock()) as mock_run_stage:
        from analysis.pipeline import start_pipeline
        await start_pipeline(ANALYSIS_ID, ["pl_1"], ["d_1"], factory)

    # run_stage must be called with stage_num=4
    mock_run_stage.assert_called_once_with(ANALYSIS_ID, 4, factory)

    # stages 1, 2, 3 must be in stage_results with status="skipped"
    assert "stage_1" in captured_stage_results, "stage_1 missing from stage_results"
    assert "stage_2" in captured_stage_results, "stage_2 missing from stage_results"
    assert "stage_3" in captured_stage_results, "stage_3 missing from stage_results"
    assert captured_stage_results["stage_1"]["status"] == "skipped"
    assert captured_stage_results["stage_2"]["status"] == "skipped"
    assert captured_stage_results["stage_3"]["status"] == "skipped"

    # stage_4 must NOT be in stage_results (it was run, not skipped)
    assert "stage_4" not in captured_stage_results


# ---------------------------------------------------------------------------
# Test 4: skipped stage dicts contain the input_mode key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skipped_stages_contain_input_mode():
    """Each skipped stage dict must contain input_mode matching the mode string."""
    for mode, expected_skipped in [
        ("manual_compounds", [1, 2]),
        ("manual_targets", [1, 2, 3]),
    ]:
        run = _make_run(input_mode=mode)
        factory, session = _make_session_factory(run)

        captured_stage_results = {}

        async def fake_update_run_status(session, analysis_id, status, **kwargs):
            sr = kwargs.get("stage_results")
            if sr:
                captured_stage_results.update(sr)
            mock_run = MagicMock()
            mock_run.status = status
            return mock_run

        with patch("analysis.pipeline.analysis_repo.get_run",
                   new=AsyncMock(return_value=run)), \
             patch("analysis.pipeline.analysis_repo.update_run_status",
                   new=AsyncMock(side_effect=fake_update_run_status)), \
             patch("analysis.pipeline.run_stage", new=AsyncMock()):
            from analysis.pipeline import start_pipeline
            await start_pipeline(ANALYSIS_ID, ["pl_1"], ["d_1"], factory)

        for n in expected_skipped:
            key = f"stage_{n}"
            assert key in captured_stage_results, \
                f"{key} missing for mode={mode}"
            entry = captured_stage_results[key]
            assert "input_mode" in entry, \
                f"{key} missing 'input_mode' key for mode={mode}"
            assert entry["input_mode"] == mode, \
                f"{key} input_mode mismatch: expected {mode!r}, got {entry['input_mode']!r}"


# ---------------------------------------------------------------------------
# Test 5: unknown _input_mode falls back to stage 1 (no skips)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_input_mode_falls_back_to_stage_1():
    """Unrecognised _input_mode value falls back to standard — stage 1 runs, no skips."""
    run = _make_run(input_mode="invalid_mode")
    factory, session = _make_session_factory(run)

    captured_stage_results = {}

    async def fake_update_run_status(session, analysis_id, status, **kwargs):
        sr = kwargs.get("stage_results")
        if sr:
            captured_stage_results.update(sr)
        mock_run = MagicMock()
        mock_run.status = status
        return mock_run

    with patch("analysis.pipeline.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("analysis.pipeline.analysis_repo.update_run_status",
               new=AsyncMock(side_effect=fake_update_run_status)), \
         patch("analysis.pipeline.run_stage", new=AsyncMock()) as mock_run_stage:
        from analysis.pipeline import start_pipeline
        await start_pipeline(ANALYSIS_ID, ["pl_1"], ["d_1"], factory)

    # run_stage must be called with stage_num=1 (fallback)
    mock_run_stage.assert_called_once_with(ANALYSIS_ID, 1, factory)

    # No skipped stages must appear in stage_results
    for key, entry in captured_stage_results.items():
        assert entry.get("status") != "skipped", \
            f"unknown mode must not write any skipped stage, but {key} has status='skipped'"
