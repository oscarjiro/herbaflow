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
