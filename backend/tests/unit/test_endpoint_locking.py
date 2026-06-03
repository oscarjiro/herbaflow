# backend/tests/unit/test_endpoint_locking.py
import inspect
from app.routers import analyses


def test_status_guarded_endpoints_read_under_lock():
    # Endpoints that check status/contents then write must perform their
    # read-modify-write under a row-level lock. They may take the lock directly
    # (get_run_locked) or via the locked read-modify-write primitive
    # (merge_stage_results_locked, which acquires get_run_locked internally and
    # commits in a single transaction). The add_user_* endpoints validate the
    # external input first (no lock held across the network call) and then merge
    # under the lock through merge_stage_results_locked.
    for fn in ("approve_stage", "reject_stage", "add_user_target",
               "add_user_disease_target", "remove_user_target",
               "remove_user_disease_target", "add_user_compound",
               "remove_user_compound"):
        src = inspect.getsource(getattr(analyses, fn))
        assert ("get_run_locked" in src
                or "merge_stage_results_locked" in src), fn
