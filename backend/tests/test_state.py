from app import contracts
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


def test_stranded_statuses_set() -> None:
    """stranded_statuses returns pending + stage_N_running for every pipeline stage;
    never includes awaiting_approval, complete, or failed."""
    statuses = state.stranded_statuses()

    # pending is always stranded
    assert "pending" in statuses

    # every pipeline stage contributes a stage_N_running entry
    for n in contracts.pipeline_stages():
        assert f"stage_{n}_running" in statuses, f"stage_{n}_running missing from stranded_statuses"

    # awaiting_approval, complete, failed are settled — never stranded
    for s in statuses:
        assert not s.endswith(
            "_awaiting_approval"
        ), f"unexpected _awaiting_approval in stranded: {s}"
    assert "complete" not in statuses
    assert "failed" not in statuses
