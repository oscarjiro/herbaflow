import uuid
from types import SimpleNamespace

import pytest

from app.pipeline import engine


class FakeRepo:
    """Dict-backed fake of AnalysisRepository for engine dispatch tests."""

    def __init__(self, run: SimpleNamespace) -> None:
        self.run = run

    async def get(self, analysis_id: uuid.UUID) -> SimpleNamespace:
        return self.run

    async def set_status(
        self, run: SimpleNamespace, status: str, *, current_stage: int | None = None
    ) -> None:
        run.status = status
        if current_stage is not None:
            run.current_stage = current_stage

    async def set_stage_result(self, run: SimpleNamespace, stage: int, result: dict) -> None:
        merged = dict(run.stage_results)
        merged[str(stage)] = result
        run.stage_results = merged

    async def complete(self, run: SimpleNamespace) -> None:
        run.status = "complete"

    async def fail(self, run: SimpleNamespace, message: str) -> None:
        run.status = "failed"
        run.error_message = message


def _run(mode: str) -> SimpleNamespace:
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        mode=mode,
        status="pending",
        current_stage=None,
        stage_results={},
        error_message=None,
        parameters={},
    )


def _compounds(n: int) -> list[dict]:
    return [{"compound_id": f"c{i}", "canonical_name": f"C{i}"} for i in range(n)]


def _runners(stage1_count: int, stage2_count: int) -> dict[int, object]:
    async def stage1_runner(run: SimpleNamespace) -> dict:
        return {"count": stage1_count, "compounds": _compounds(stage1_count), "state": "computed"}

    async def stage2_runner(run: SimpleNamespace) -> dict:
        return {
            "count": stage2_count,
            "passed": [],
            "filtered": [],
            "annotations": {},
            "state": "computed",
        }

    return {1: stage1_runner, 2: stage2_runner}


@pytest.mark.asyncio
async def test_guided_pauses_then_advances_through_both_stages() -> None:
    run = _run("guided")
    repo = FakeRepo(run)
    runners = _runners(3, 2)

    await engine.execute_run(repo, run.analysis_id, runners)
    assert run.status == "stage_1_awaiting_approval"
    assert run.current_stage == 1

    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_2_awaiting_approval"
    assert run.current_stage == 2

    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "complete"


@pytest.mark.asyncio
async def test_auto_chains_to_complete() -> None:
    run = _run("auto")
    repo = FakeRepo(run)
    runners = _runners(3, 2)

    await engine.execute_run(repo, run.analysis_id, runners)
    assert run.status == "complete"
    assert run.stage_results["1"]["count"] == 3
    assert run.stage_results["2"]["count"] == 2
    assert run.current_stage == 2


@pytest.mark.asyncio
async def test_auto_stage2_zero_pass_fails_with_empty_state_message() -> None:
    run = _run("auto")
    repo = FakeRepo(run)
    runners = _runners(5, 0)

    await engine.execute_run(repo, run.analysis_id, runners)
    assert run.status == "failed"
    assert "skip_adme" in run.error_message
    assert "5" in run.error_message


@pytest.mark.asyncio
async def test_guided_stage2_zero_pass_awaits_approval_not_failed() -> None:
    run = _run("guided")
    repo = FakeRepo(run)
    runners = _runners(5, 0)

    # advance past the stage-1 checkpoint into stage 2
    await engine.execute_run(repo, run.analysis_id, runners)
    assert run.status == "stage_1_awaiting_approval"

    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_2_awaiting_approval"
    assert run.error_message is None


@pytest.mark.asyncio
async def test_stage1_zero_fails() -> None:
    run = _run("auto")
    repo = FakeRepo(run)
    runners = _runners(0, 0)

    await engine.execute_run(repo, run.analysis_id, runners)
    assert run.status == "failed"
    assert "compound" in run.error_message.lower()
