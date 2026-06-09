from app.pipeline import state


def test_is_settled_terminal_statuses() -> None:
    assert state.is_settled(state.COMPLETE) is True
    assert state.is_settled(state.FAILED) is True


def test_is_settled_awaiting_approval() -> None:
    assert state.is_settled("stage_1_awaiting_approval") is True
    assert state.is_settled("stage_2_awaiting_approval") is True


def test_is_settled_running_is_not_settled() -> None:
    assert state.is_settled("stage_1_running") is False
    assert state.is_settled("stage_2_starting") is False
    assert state.is_settled(state.PENDING) is False


def test_is_settled_none() -> None:
    assert state.is_settled(None) is False
