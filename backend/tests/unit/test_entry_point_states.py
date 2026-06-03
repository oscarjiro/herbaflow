import asyncio
from analysis import stage_state


def test_setdefault_stamps_computed_but_respects_existing():
    # The central stamp is a setdefault: it fills "computed" only when absent.
    computed_result = {"foo": 1}
    computed_result.setdefault("state", stage_state.COMPUTED)
    assert computed_result["state"] == "computed"

    user_result = {"state": stage_state.USER_PROVIDED}
    user_result.setdefault("state", stage_state.COMPUTED)
    assert user_result["state"] == "user_provided"  # not overridden


from analysis.pipeline import _FIRST_REAL_STAGE


def test_manual_compounds_entry_is_stage_two():
    assert _FIRST_REAL_STAGE["manual_compounds"] == 2


def _na_states(input_mode, first_real, existing_stage_results):
    """Mirror of the start_pipeline N/A-writer rule, isolated for unit testing."""
    from analysis import stage_state
    out = {}
    for n in range(1, first_real):
        if f"stage_{n}" not in existing_stage_results:
            out[f"stage_{n}"] = {"state": stage_state.NOT_APPLICABLE}
    return out


def test_manual_targets_marks_only_empty_preentry_stages():
    # inject wrote stage_3; stages 1+2 are empty → only those become not_applicable.
    existing = {"stage_3": {"state": "user_provided"}}
    na = _na_states("manual_targets", 4, existing)
    assert set(na) == {"stage_1", "stage_2"}
    assert "stage_3" not in na  # entry stage spared (no clobber)


def test_manual_compounds_writes_no_na_stages():
    # inject wrote stage_1; entry is stage 2 → nothing left to mark not_applicable.
    existing = {"stage_1": {"state": "user_provided"}}
    na = _na_states("manual_compounds", 2, existing)
    assert na == {}
