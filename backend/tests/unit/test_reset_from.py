"""Unit tests for the extended reset_run_from_stage repository function.

Tests param_overrides merging behaviour without hitting the DB.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID


# ---------------------------------------------------------------------------
# Helper: build a mock AnalysisRun
# ---------------------------------------------------------------------------

def _make_run(parameters: dict | None = None, stage_results: dict | None = None):
    run = MagicMock()
    run.analysis_id = UUID("00000000-0000-0000-0000-000000000001")
    run.parameters = dict(parameters or {})
    run.stage_results = dict(stage_results or {})
    run.status = "stage_2_awaiting_approval"
    run.current_stage = 2
    run.updated_at = None
    run.completed_at = None
    run.expires_at = None
    run.error_message = None
    return run


# ---------------------------------------------------------------------------
# Tests for param override merging logic (pure logic extracted from repo)
# ---------------------------------------------------------------------------

def _merge_params(existing: dict, overrides: dict) -> dict:
    """Replicate the merge logic from reset_run_from_stage."""
    merged = dict(existing)
    for key, val in overrides.items():
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged.get(key, {}), **val}
        else:
            merged[key] = val
    return merged


class TestParamMergeLogic:
    def test_deep_merge_dict_values(self):
        existing = {"adme": {"max_mw": 500.0, "max_logp": 5.0}}
        overrides = {"adme": {"max_mw": 600.0}}
        result = _merge_params(existing, overrides)
        assert result["adme"]["max_mw"] == 600.0
        assert result["adme"]["max_logp"] == 5.0  # preserved

    def test_replace_non_dict_value(self):
        existing = {"adme": {"max_mw": 500.0}}
        overrides = {"some_key": "new_value"}
        result = _merge_params(existing, overrides)
        assert result["some_key"] == "new_value"
        assert result["adme"]["max_mw"] == 500.0  # unchanged

    def test_new_param_group_added(self):
        existing = {"adme": {"max_mw": 500.0}}
        overrides = {"ppi": {"min_confidence": 0.7}}
        result = _merge_params(existing, overrides)
        assert result["ppi"]["min_confidence"] == 0.7
        assert result["adme"]["max_mw"] == 500.0  # unchanged

    def test_internal_keys_preserved_on_deep_merge(self):
        existing = {"_plant_ids": ["a", "b"], "_disease_id": "c", "adme": {"max_mw": 500.0}}
        overrides = {"adme": {"max_mw": 600.0}}
        result = _merge_params(existing, overrides)
        assert result["_plant_ids"] == ["a", "b"]
        assert result["_disease_id"] == "c"
        assert result["adme"]["max_mw"] == 600.0

    def test_empty_overrides_no_change(self):
        existing = {"adme": {"max_mw": 500.0}}
        result = _merge_params(existing, {})
        assert result == existing

    def test_replace_when_existing_not_dict(self):
        existing = {"adme": "old_string_value"}
        overrides = {"adme": {"max_mw": 600.0}}
        result = _merge_params(existing, overrides)
        # existing["adme"] is a string, not dict → replace (not deep merge)
        assert result["adme"] == {"max_mw": 600.0}

    def test_multiple_groups_merged_independently(self):
        existing = {
            "adme": {"max_mw": 500.0, "max_logp": 5.0},
            "target": {"min_pchembl": 5.0, "human_only": True},
        }
        overrides = {
            "adme": {"max_mw": 700.0},
            "target": {"min_pchembl": 6.0},
        }
        result = _merge_params(existing, overrides)
        assert result["adme"] == {"max_mw": 700.0, "max_logp": 5.0}
        assert result["target"] == {"min_pchembl": 6.0, "human_only": True}


# ---------------------------------------------------------------------------
# Integration-style: test reset_run_from_stage with mocked session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_run_from_stage_no_overrides_preserves_params():
    """Calling without param_overrides must not touch run.parameters."""
    from app.repositories.analysis_repo import reset_run_from_stage

    existing_params = {"adme": {"max_mw": 500.0}, "_plant_ids": ["a"]}
    run = _make_run(parameters=existing_params, stage_results={"stage_2": {"foo": 1}, "stage_3": {"bar": 2}})

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    with patch("app.repositories.analysis_repo.get_run", new=AsyncMock(return_value=run)):
        result = await reset_run_from_stage(session, run.analysis_id, from_stage=2)

    # Parameters unchanged
    assert result.parameters["adme"]["max_mw"] == 500.0
    # Stage 2 and beyond cleared
    assert "stage_2" not in result.stage_results
    assert "stage_3" not in result.stage_results


@pytest.mark.asyncio
async def test_reset_run_from_stage_with_overrides_merges_params():
    """Calling with param_overrides must deep-merge into run.parameters."""
    from app.repositories.analysis_repo import reset_run_from_stage

    existing_params = {"adme": {"max_mw": 500.0, "max_logp": 5.0}, "_plant_ids": ["a"]}
    run = _make_run(parameters=existing_params, stage_results={"stage_2": {"foo": 1}})

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    overrides = {"adme": {"max_mw": 600.0}}

    with patch("app.repositories.analysis_repo.get_run", new=AsyncMock(return_value=run)):
        result = await reset_run_from_stage(
            session, run.analysis_id, from_stage=2, param_overrides=overrides
        )

    assert result.parameters["adme"]["max_mw"] == 600.0
    assert result.parameters["adme"]["max_logp"] == 5.0  # preserved
    assert result.parameters["_plant_ids"] == ["a"]  # internal key preserved
    assert "stage_2" not in result.stage_results


@pytest.mark.asyncio
async def test_reset_run_from_stage_status_set_correctly_for_stage_gt_1():
    """Stage > 1 resets to stage_{n-1}_awaiting_approval."""
    from app.repositories.analysis_repo import reset_run_from_stage

    run = _make_run(stage_results={"stage_3": {}, "stage_4": {}})

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    with patch("app.repositories.analysis_repo.get_run", new=AsyncMock(return_value=run)):
        result = await reset_run_from_stage(session, run.analysis_id, from_stage=3)

    assert result.status == "stage_2_awaiting_approval"
    assert result.current_stage == 2
    assert "stage_3" not in result.stage_results
    assert "stage_4" not in result.stage_results


@pytest.mark.asyncio
async def test_reset_run_from_stage_stage_1_sets_pending():
    """Stage 1 reset sets status to pending and current_stage to None."""
    from app.repositories.analysis_repo import reset_run_from_stage

    run = _make_run(stage_results={"stage_1": {}, "stage_2": {}})
    run.status = "stage_1_awaiting_approval"
    run.current_stage = 1

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    with patch("app.repositories.analysis_repo.get_run", new=AsyncMock(return_value=run)):
        result = await reset_run_from_stage(session, run.analysis_id, from_stage=1)

    assert result.status == "pending"
    assert result.current_stage is None
