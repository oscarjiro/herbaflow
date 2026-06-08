import pytest

from app.pipeline import state


def test_stage_status_composes() -> None:
    assert state.stage_status(1, "running") == "stage_1_running"
    assert state.stage_status(1, "awaiting_approval") == "stage_1_awaiting_approval"


def test_stage_status_rejects_unknown_phase() -> None:
    with pytest.raises(ValueError):
        state.stage_status(1, "bogus")


def test_terminal_detection() -> None:
    assert state.is_terminal("complete")
    assert state.is_terminal("failed")
    assert not state.is_terminal("stage_1_running")
    assert not state.is_terminal("pending")
