"""Unit tests for pipeline skip logic (T4.5).

Tests that start_pipeline() reads _input_mode from run.parameters and:
- skips the appropriate stages (writing sentinel dicts to stage_results)
- calls run_stage() at the correct first real stage number
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

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
        await start_pipeline(ANALYSIS_ID, ["pl_1"], "d_1", factory)

    # run_stage must be called with stage_num=1
    mock_run_stage.assert_called_once_with(ANALYSIS_ID, 1, factory)

    # No skipped stages written to stage_results
    for key, entry in captured_stage_results.items():
        assert entry.get("status") != "skipped", \
            f"standard mode must not write any skipped stage, but {key} has status='skipped'"


# ---------------------------------------------------------------------------
# Test 2: manual_compounds → empty stage 1 marked not_applicable, stage 2 runs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_compounds_marks_empty_stage_1():
    """input_mode=manual_compounds: empty stage 1 is not_applicable, stage 2 runs live."""
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
        await start_pipeline(ANALYSIS_ID, ["pl_1"], "d_1", factory)

    # run_stage must be called with stage_num=2 (ADME runs live for manual compounds)
    mock_run_stage.assert_called_once_with(ANALYSIS_ID, 2, factory)

    # stage 1 was empty → marked not_applicable
    assert "stage_1" in captured_stage_results, "stage_1 missing from stage_results"
    assert captured_stage_results["stage_1"]["state"] == "not_applicable"

    # stage_2 must NOT be in stage_results (it was run, not marked)
    assert "stage_2" not in captured_stage_results


# ---------------------------------------------------------------------------
# Test 3: manual_targets → empty stages 1–3 not_applicable, run_stage called with 4
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_targets_marks_empty_stages_1_2_3():
    """input_mode=manual_targets: empty stages 1, 2, 3 are not_applicable, stage 4 runs."""
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
        await start_pipeline(ANALYSIS_ID, ["pl_1"], "d_1", factory)

    # run_stage must be called with stage_num=4
    mock_run_stage.assert_called_once_with(ANALYSIS_ID, 4, factory)

    # stages 1, 2, 3 were empty → all marked not_applicable
    assert "stage_1" in captured_stage_results, "stage_1 missing from stage_results"
    assert "stage_2" in captured_stage_results, "stage_2 missing from stage_results"
    assert "stage_3" in captured_stage_results, "stage_3 missing from stage_results"
    assert captured_stage_results["stage_1"]["state"] == "not_applicable"
    assert captured_stage_results["stage_2"]["state"] == "not_applicable"
    assert captured_stage_results["stage_3"]["state"] == "not_applicable"

    # stage_4 must NOT be in stage_results (it was run, not marked)
    assert "stage_4" not in captured_stage_results


@pytest.mark.asyncio
async def test_manual_targets_spares_injected_stage_3():
    """A stage already populated by inject (stage_3 user_provided) is never clobbered."""
    run = _make_run(input_mode="manual_targets")
    run.stage_results = {"stage_3": {"state": "user_provided"}}
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
        await start_pipeline(ANALYSIS_ID, ["pl_1"], "d_1", factory)

    mock_run_stage.assert_called_once_with(ANALYSIS_ID, 4, factory)

    # only the genuinely-empty pre-entry stages were marked
    assert captured_stage_results["stage_1"]["state"] == "not_applicable"
    assert captured_stage_results["stage_2"]["state"] == "not_applicable"
    # stage_3 must NOT be overwritten — the injected user_provided entry is spared
    assert "stage_3" not in captured_stage_results


# ---------------------------------------------------------------------------
# Test 4: empty pre-entry stage dicts carry state="not_applicable"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_preentry_stages_marked_not_applicable():
    """Each genuinely-empty pre-entry stage dict must carry state='not_applicable'."""
    for mode, expected_marked in [
        ("manual_compounds", [1]),
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
            await start_pipeline(ANALYSIS_ID, ["pl_1"], "d_1", factory)

        for n in expected_marked:
            key = f"stage_{n}"
            assert key in captured_stage_results, \
                f"{key} missing for mode={mode}"
            entry = captured_stage_results[key]
            assert entry.get("state") == "not_applicable", \
                f"{key} expected state='not_applicable' for mode={mode}, got {entry!r}"


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
        await start_pipeline(ANALYSIS_ID, ["pl_1"], "d_1", factory)

    # run_stage must be called with stage_num=1 (fallback)
    mock_run_stage.assert_called_once_with(ANALYSIS_ID, 1, factory)

    # No skipped stages must appear in stage_results
    for key, entry in captured_stage_results.items():
        assert entry.get("status") != "skipped", \
            f"unknown mode must not write any skipped stage, but {key} has status='skipped'"
