import uuid
from types import SimpleNamespace

import pytest

from app.errors import ConflictProblem
from app.pipeline import engine


class FakeRepo:
    def __init__(self, run):
        self.run = run

    async def get(self, analysis_id):
        return self.run

    async def set_status(self, run, status, *, current_stage=None):
        run.status = status
        if current_stage is not None:
            run.current_stage = current_stage

    async def set_stage_result(self, run, stage, result):
        run.stage_results[str(stage)] = result

    async def complete(self, run):
        run.status = "complete"

    async def fail(self, run, message):
        run.status = "failed"
        run.error_message = message


def _run(mode):
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        mode=mode,
        status="pending",
        current_stage=None,
        stage_results={},
        error_message=None,
        parameters={"plant_ids": [str(uuid.uuid4())]},
    )


def _compounds(n):
    return [{"compound_id": f"c{i}", "canonical_name": f"C{i}"} for i in range(n)]


def _runners(stage1_count, stage2_count):
    async def stage1_runner(r):
        return {
            "count": stage1_count,
            "compounds": _compounds(stage1_count),
            "per_plant": {},
            "state": "computed",
        }

    async def stage2_runner(r):
        return {
            "count": stage2_count,
            "passed": [],
            "filtered": [],
            "annotations": {},
            "state": "computed",
        }

    return {1: stage1_runner, 2: stage2_runner}


@pytest.mark.asyncio
async def test_auto_runs_to_complete() -> None:
    run = _run("auto")
    repo = FakeRepo(run)

    await engine.execute_run(repo, run.analysis_id, _runners(2, 1))

    assert run.status == "complete"
    assert run.stage_results["1"]["count"] == 2


@pytest.mark.asyncio
async def test_guided_pauses_for_approval() -> None:
    run = _run("guided")
    repo = FakeRepo(run)
    runners = _runners(1, 1)

    await engine.execute_run(repo, run.analysis_id, runners)
    assert run.status == "stage_1_awaiting_approval"

    # Approving stage 1 runs stage 2, which (guided) pauses again.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_2_awaiting_approval"

    # Approving the last runnable stage completes the run.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "complete"


@pytest.mark.asyncio
async def test_zero_compounds_fails() -> None:
    run = _run("auto")
    repo = FakeRepo(run)

    await engine.execute_run(repo, run.analysis_id, _runners(0, 0))
    assert run.status == "failed"
    assert "compound" in run.error_message.lower()


@pytest.mark.asyncio
async def test_advance_rejects_wrong_state() -> None:
    run = _run("guided")
    run.status = "stage_1_running"
    repo = FakeRepo(run)
    with pytest.raises(ConflictProblem):
        await engine.advance_run(repo, run.analysis_id, _runners(1, 1))
