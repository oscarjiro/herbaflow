# backend/tests/unit/test_endpoint_locking.py
import inspect
from app.routers import analyses


def test_status_guarded_endpoints_read_under_lock():
    # Endpoints that check status/contents then write must read the run with the lock.
    for fn in ("approve_stage", "reject_stage", "add_user_target",
               "add_user_disease_target", "remove_user_target",
               "remove_user_disease_target", "add_user_compound",
               "remove_user_compound"):
        src = inspect.getsource(getattr(analyses, fn))
        assert "get_run_locked" in src, fn
