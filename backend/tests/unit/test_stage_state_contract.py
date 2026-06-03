from app.contracts import STAGE_STATES
from analysis import stage_state


def test_contract_exposes_three_states():
    assert set(STAGE_STATES) == {"computed", "user_provided", "not_applicable"}


def test_constants_module_matches_contract():
    assert set(stage_state.ALL) == set(STAGE_STATES)
    assert stage_state.COMPUTED == "computed"
    assert stage_state.USER_PROVIDED == "user_provided"
    assert stage_state.NOT_APPLICABLE == "not_applicable"
