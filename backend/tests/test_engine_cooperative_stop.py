# backend/tests/test_engine_cooperative_stop.py
import uuid

import pytest

from app.pipeline import engine


class FakeRepo:
    """In-memory repo; `get` returns None after `gone_after` calls (simulates a delete)."""

    def __init__(self, run, gone_after: int) -> None:
        self._run = run
        self._gone_after = gone_after
        self.get_calls = 0
        self.committed = 0

    async def get(self, analysis_id):
        self.get_calls += 1
        return None if self.get_calls > self._gone_after else self._run

    async def set_status(self, run, status, *, current_stage=None):
        pass

    async def set_stage_result(self, run, stage, result):
        pass

    async def clear_stage_results(self, run, stages):
        pass

    async def mark_stages_stale(self, run, stages):
        pass

    async def set_parameters(self, run):
        pass

    async def complete(self, run):
        pass

    async def fail(self, run, message):
        pass

    async def commit(self):
        self.committed += 1


class FakeRun:
    parameters = {"plant_ids": []}
    mode = "auto"
    stage_results: dict = {}
    current_stage = 0


@pytest.mark.asyncio
async def test_execute_run_stops_when_run_deleted_midway() -> None:
    run = FakeRun()
    # get() is called once before the loop, then once at the top of each stage iteration.
    # gone_after=2 => pre-loop(1) + stage-1 top(2) return the run; stage-2 top(3) returns None.
    repo = FakeRepo(run, gone_after=2)
    ran: list[int] = []

    async def runner(_run):
        ran.append(len(ran) + 1)
        # Stage 1 is an ENTITY stage: the engine folds the edit layer over result["compounds"]
        # and RECOMPUTES count from it. Return one computed compound so stage 1 does NOT
        # hard-stop on an empty entity set — the loop must reach stage 2, where the delete is seen.
        return {
            "count": 1,
            "compounds": [{"compound_id": str(uuid.uuid4()), "canonical_name": "c"}],
        }

    runners = {s: runner for s in engine.RUNNABLE_STAGES}
    await engine.execute_run(repo, uuid.uuid4(), runners, start_stage=1)

    # Stage 1 ran; the run vanished at the stage-2 boundary, so no further stages executed.
    assert ran == [1]
    # Prove the cooperative path was actually taken (NOT a stage-1 empty hard-stop):
    assert repo.get_calls == 3  # pre-loop + stage-1 top + stage-2 top (None -> stop)
    # Stage 1 commits twice (loop-head commit + the running-status commit that makes the
    # executing stage visible to pollers); stage 2 does only its loop-head commit before the
    # delete is detected and the run stops.
    assert repo.committed == 3
