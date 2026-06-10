"""Unit tests for the deferred (``defer=True``) prepare path of the engine.

In ``defer`` mode ``advance_run`` / ``reset_from`` must do all the synchronous
state mutation (set the start stage ``*_running``, clear downstream) and RETURN the
start stage WITHOUT running any stage — the slow run is scheduled as a BackgroundTask
by the router. ``defer=False`` (the default, exercised by the existing suites) runs
inline and returns ``None``.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app import contracts
from app.pipeline import edits, engine


class _FakeRepo:
    def __init__(self, run: SimpleNamespace) -> None:
        self.run = run
        self.session = SimpleNamespace()
        self.cleared: list[set[int]] = []

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

    async def clear_stage_results(self, run: SimpleNamespace, stages: set[int]) -> None:
        self.cleared.append(set(stages))
        run.stage_results = {k: v for k, v in run.stage_results.items() if int(k) not in stages}

    async def set_parameters(self, run: SimpleNamespace) -> None:
        return None

    async def complete(self, run: SimpleNamespace) -> None:
        run.status = "complete"

    async def fail(self, run: SimpleNamespace, message: str) -> None:
        run.status = "failed"
        run.error_message = message


def _runners_that_must_not_run() -> dict[int, Any]:
    async def _boom(_run: SimpleNamespace) -> dict:
        raise AssertionError("defer mode must not execute a stage runner")

    return {1: _boom, 2: _boom, 3: _boom}


def _s1_fragment(ids: list[str]) -> dict[str, Any]:
    entities = [{"compound_id": i, "canonical_name": f"C-{i}"} for i in ids]
    return edits.build_stage_entities(entities, None)


def _awaiting_run() -> SimpleNamespace:
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        mode="guided",
        status="stage_1_awaiting_approval",
        current_stage=1,
        error_message=None,
        parameters={
            "plant_ids": [str(uuid.uuid4())],
            "manual_compounds": [],
            "stage_edits": {},
            "adme": dict(contracts.adme_defaults()),
        },
        stage_results={
            "1": _s1_fragment(["a", "b"]),
        },
    )


@pytest.mark.asyncio
async def test_advance_defer_returns_next_stage_and_sets_running_without_executing() -> None:
    run = _awaiting_run()
    repo = _FakeRepo(run)

    start = await engine.advance_run(
        repo, run.analysis_id, _runners_that_must_not_run(), defer=True
    )

    assert start == 2
    assert run.status == "stage_2_running"
    assert run.current_stage == 2


@pytest.mark.asyncio
async def test_advance_defer_at_last_stage_completes_and_returns_none() -> None:
    run = _awaiting_run()
    run.status = "stage_4_awaiting_approval"
    run.current_stage = 4

    repo = _FakeRepo(run)

    start = await engine.advance_run(
        repo, run.analysis_id, _runners_that_must_not_run(), defer=True
    )

    assert start is None  # nothing left to run
    assert run.status == "complete"


@pytest.mark.asyncio
async def test_reset_from_defer_param_redo_returns_start_and_clears_downstream() -> None:
    run = _awaiting_run()
    run.status = "complete"
    run.current_stage = 2
    run.stage_results["2"] = {"count": 2, "passed": [], "filtered": [], "state": "computed"}
    repo = _FakeRepo(run)

    start = await engine.reset_from(
        repo,
        run.analysis_id,
        2,
        _runners_that_must_not_run(),
        param_overrides={"max_violations": 0},
        defer=True,
    )

    assert start == 2
    assert run.status == "stage_2_running"
    assert {2} in repo.cleared
    assert run.parameters["adme"]["max_violations"] == 0


@pytest.mark.asyncio
async def test_reset_from_defer_set_edit_s1_returns_runnable_dependent() -> None:
    run = _awaiting_run()
    run.status = "stage_2_awaiting_approval"
    run.current_stage = 2
    run.stage_results["2"] = {"count": 2, "passed": [], "filtered": [], "state": "computed"}
    repo = _FakeRepo(run)

    # set edit (param_overrides=None) on stage 1 -> nearest runnable dependent is stage 2.
    start = await engine.reset_from(
        repo, run.analysis_id, 1, _runners_that_must_not_run(), defer=True
    )

    assert start == 2
    assert run.status == "stage_2_running"
    assert {2} in repo.cleared
