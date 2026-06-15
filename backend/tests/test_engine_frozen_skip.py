"""Engine frozen-stage skip (entry-modes) — fake repo + recording runners.

Proves the engine SKIPS user-provided / not-applicable stages (the frozen set derived from a
run's ``input_modes``) on ``execute_run``; allows a frozen stage as a SET-EDIT reset target
(reruns only its downstream closure) but refuses it as a PARAM-Redo target on ``reset_from``;
while a run with no ``input_modes`` (pre-entry-modes / selection) keeps every stage runnable.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.errors import ValidationProblem
from app.pipeline import engine


class _FakeRepo:
    def __init__(self, run: Any) -> None:
        self._run = run
        self.cleared: set[int] = set()

    async def get(self, _id: uuid.UUID) -> Any:
        return self._run

    async def set_status(self, run: Any, status: str, *, current_stage: int | None = None) -> None:
        run.status = status
        if current_stage is not None:
            run.current_stage = current_stage

    async def set_stage_result(self, run: Any, stage: int, result: dict[str, Any]) -> None:
        run.stage_results[str(stage)] = result

    async def clear_stage_results(self, run: Any, stages: set[int]) -> None:
        self.cleared |= stages
        for s in stages:
            run.stage_results.pop(str(s), None)

    async def mark_stages_stale(self, run: Any, stages: set[int]) -> None:
        for s in stages:
            if str(s) in run.stage_results:
                run.stage_results[str(s)]["stale"] = True

    async def set_parameters(self, run: Any) -> None:
        return None

    async def complete(self, run: Any) -> None:
        run.status = "complete"

    async def fail(self, run: Any, message: str) -> None:
        run.status = "failed"
        run.error_message = message

    async def commit(self) -> None:
        pass


class _Run:
    def __init__(
        self,
        *,
        modes: dict[str, str],
        mode: str = "auto",
        stage_results: dict[str, Any] | None = None,
    ) -> None:
        self.parameters: dict[str, Any] = {"input_modes": modes}
        self.stage_results: dict[str, Any] = stage_results or {}
        self.status: str | None = "pending"
        self.current_stage: int | None = None
        self.mode = mode
        self.error_message: str | None = None


def _recording_runners(ran: list[int]) -> dict[int, Any]:
    """Runners that record which stages fired and return a result that survives the engine.

    Entity stages (1/3/4) run their output through ``edits.build_stage_entities`` keyed on either
    ``compounds`` or ``targets``; a 0-length entity list would trip the empty-stage hard-stop. So
    every runner returns BOTH list keys with one synthetic entity, plus a non-zero ``count`` for
    the non-entity stages — keeping all stages alive so the test isolates the SKIP behavior.
    """

    def make(s: int):
        async def runner(_run: Any) -> dict[str, Any]:
            ran.append(s)
            return {
                "count": 1,
                "state": "computed",
                "compounds": [{"compound_id": "c", "canonical_name": "x"}],
                "targets": [{"target_id": "t", "canonical_name": "x"}],
            }

        return runner

    return {s: make(s) for s in range(1, 9)}


@pytest.mark.asyncio
async def test_auto_skips_mid_range_frozen_s4() -> None:
    """selection + manual_disease_targets: S4 is user-provided -> engine skips it mid-run."""
    ran: list[int] = []
    run = _Run(
        modes={"plant": "selection", "disease": "manual_disease_targets"},
        stage_results={"4": {"state": "user_provided", "count": 2}},
    )
    await engine.execute_run(_FakeRepo(run), uuid.uuid4(), _recording_runners(ran))
    assert 4 not in ran
    assert ran == [1, 2, 3, 5, 6, 7, 8]
    # The pre-filled frozen stage is preserved untouched.
    assert run.stage_results["4"]["state"] == "user_provided"


@pytest.mark.asyncio
async def test_auto_skips_frozen_prefix_manual_targets() -> None:
    """manual_targets + selection: S1/S2 not_applicable, S3 user_provided -> compute from S4."""
    ran: list[int] = []
    run = _Run(
        modes={"plant": "manual_targets", "disease": "selection"},
        stage_results={
            "1": {"state": "not_applicable", "count": 0},
            "2": {"state": "not_applicable", "count": 0},
            "3": {"state": "user_provided", "count": 3, "targets": []},
        },
    )
    await engine.execute_run(_FakeRepo(run), uuid.uuid4(), _recording_runners(ran))
    assert ran == [4, 5, 6, 7, 8]


@pytest.mark.asyncio
async def test_reset_from_set_edit_allows_frozen_stage() -> None:
    """A SET EDIT (no param overrides) may reset from a frozen (user-provided) stage.

    The frozen stage itself is never recomputed — ``edit_stage`` already re-derived it in place;
    a set-edit reset only re-runs the (non-frozen) downstream closure. So re-running from a
    user-provided S3 yields the downstream run-set S5..S8 (the recovery path after editing manual
    targets), NOT a 422. Regression guard for the dead-recompute bug on user-provided entity stages.
    """
    run = _Run(
        modes={"plant": "manual_targets", "disease": "selection"},
        mode="guided",
        stage_results={
            "3": {"state": "user_provided", "count": 3},
            "4": {"count": 5, "state": "computed"},
        },
    )
    run.status = "stage_4_awaiting_approval"
    run.current_stage = 4
    run_set = await engine.reset_from(
        _FakeRepo(run), uuid.uuid4(), 3, _recording_runners([]), param_overrides=None, defer=True
    )
    assert run_set == frozenset({5, 6, 7, 8})


@pytest.mark.asyncio
async def test_reset_from_param_redo_refuses_frozen_stage() -> None:
    """A PARAM Redo of a frozen (user-provided) stage stays refused — nothing to recompute."""
    run = _Run(
        modes={"plant": "manual_targets", "disease": "selection"},
        mode="guided",
        stage_results={
            "3": {"state": "user_provided", "count": 3},
            "4": {"count": 5, "state": "computed"},
        },
    )
    run.status = "stage_4_awaiting_approval"
    run.current_stage = 4
    with pytest.raises(ValidationProblem):
        await engine.reset_from(
            _FakeRepo(run),
            uuid.uuid4(),
            3,
            _recording_runners([]),
            param_overrides={"min_pchembl": 6},
        )
