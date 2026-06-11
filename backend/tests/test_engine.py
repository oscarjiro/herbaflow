import uuid
from types import SimpleNamespace

import pytest

from app.errors import ConflictProblem
from app.pipeline import engine
from app.pipeline.stages import stage5


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


def _targets(n):
    return [{"target_id": f"t{i}", "canonical_name": f"T{i}"} for i in range(n)]


def _runners(stage1_count, stage2_count, stage3_count=1, stage4_count=1):
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

    async def stage3_runner(r):
        return {
            "targets": _targets(stage3_count),
            "compound_targets": [],
            "per_compound": {},
            "coverage_pct": 0.0,
            "count": stage3_count,
            "state": "computed",
        }

    async def stage4_runner(r):
        return {
            "targets": _targets(stage4_count),
            "disease_targets": [{"target_id": f"t{i}", "score": 0.5} for i in range(stage4_count)],
            "count": stage4_count,
            "min_score_applied": 0.3,
            "state": "computed",
        }

    async def stage5_runner(r):
        return await stage5.run(None, r)

    async def stage6_runner(r):
        # Engine-dispatch fake: a ready-made computed PPI result (no STRING call).
        return {
            "state": "computed",
            "nodes": [{"gene_symbol": "G0", "string_id": None}],
            "edges": [],
            "node_count": 1,
            "edge_count": 0,
            "count": 1,
        }

    return {
        1: stage1_runner,
        2: stage2_runner,
        3: stage3_runner,
        4: stage4_runner,
        5: stage5_runner,
        6: stage6_runner,
    }


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

    # Approving stage 2 runs stage 3, which (guided) pauses at the S3 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_3_awaiting_approval"

    # Approving stage 3 runs stage 4, which (guided) pauses at the S4 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_4_awaiting_approval"

    # Approving stage 4 runs stage 5 (overlap), which (guided) pauses at the S5 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_5_awaiting_approval"

    # Approving stage 5 runs stage 6 (PPI), which (guided) pauses at the S6 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_6_awaiting_approval"

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


@pytest.mark.asyncio
async def test_auto_fails_on_empty_stage3() -> None:
    run = _run("auto")
    repo = FakeRepo(run)
    await engine.execute_run(repo, run.analysis_id, _runners(2, 2, stage3_count=0))
    assert run.status == "failed"
    assert "step 3" in run.error_message.lower()


@pytest.mark.asyncio
async def test_auto_fails_on_empty_stage4() -> None:
    run = _run("auto")
    repo = FakeRepo(run)
    await engine.execute_run(repo, run.analysis_id, _runners(2, 2, stage4_count=0))
    assert run.status == "failed"
    assert "step 4" in run.error_message.lower()


@pytest.mark.asyncio
async def test_guided_parks_empty_stage3_then_refuses_advance() -> None:
    run = _run("guided")
    repo = FakeRepo(run)
    runners = _runners(1, 1, stage3_count=0)

    await engine.execute_run(repo, run.analysis_id, runners)  # park S1
    await engine.advance_run(repo, run.analysis_id, runners)  # run S2, park S2
    await engine.advance_run(repo, run.analysis_id, runners)  # run S3 (0), park S3
    assert run.status == "stage_3_awaiting_approval"
    assert run.stage_results["3"]["count"] == 0

    # Approving an empty stage is refused.
    with pytest.raises(ConflictProblem):
        await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_3_awaiting_approval"  # unchanged
