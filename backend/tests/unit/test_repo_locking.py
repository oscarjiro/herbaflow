# backend/tests/unit/test_repo_locking.py
import inspect

from app.repositories import analysis_repo


def test_get_run_locked_exists_and_uses_for_update():
    assert hasattr(analysis_repo, "get_run_locked")
    src = inspect.getsource(analysis_repo.get_run_locked)
    assert "with_for_update" in src


def test_mutating_writers_use_locked_read():
    for fn in ("merge_run_parameters", "reset_run_from_stage", "update_run_status"):
        src = inspect.getsource(getattr(analysis_repo, fn))
        assert "get_run_locked" in src, fn
