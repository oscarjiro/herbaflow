"""Run orchestration: a multi-stage dispatch loop over a stage registry + DAG.

The engine drives a run through the pipeline state machine. Guided runs pause for
approval after each checkpoint stage; auto runs chain to the end of the runnable
stages. The dependency DAG (``DEPENDENTS`` + ``downstream_closure``) is the project's
cross-chunk leaf topology and is reused unchanged by reset/edit logic.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app import db
from app.errors import ConflictProblem
from app.pipeline import state
from app.pipeline.stages import stage1, stage2
from app.repositories.analysis import AnalysisRepository

logger = logging.getLogger("herbaflow.pipeline")

StageRunner = Callable[[Any], Awaitable[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Dependency DAG: direct downstream consumers of each stage.
# S1->S2->S3 and S4 both feed S5; S5 feeds S6 AND S8; S6 feeds S7; S7 and S8 are leaves.
# (Leaf topology per the cross-chunk decisions ledger; the S6/S7/S8 runners land in
# later chunks.) S7 and S8 are PARALLEL leaves — S8 depends on S5, not S7.
# ---------------------------------------------------------------------------
DEPENDENTS: dict[int, set[int]] = {
    1: {2},
    2: {3},
    3: {5},
    4: {5},
    5: {6, 8},
    6: {7},
    7: set(),
    8: set(),
}


def downstream_closure(stage: int) -> set[int]:
    """All stages transitively downstream of ``stage`` (its dependents, recursively)."""
    seen: set[int] = set()
    frontier = set(DEPENDENTS.get(stage, set()))
    while frontier:
        s = frontier.pop()
        seen.add(s)
        frontier |= DEPENDENTS.get(s, set()) - seen
    return seen


# ---------------------------------------------------------------------------
# Stage registry. Extended as stages land in later chunks.
# ---------------------------------------------------------------------------
STAGE_PARAM_GROUP: dict[int, str] = {2: "adme"}  # extended per chunk (3 -> target, ...)
RUNNABLE_STAGES: tuple[int, ...] = (1, 2)  # extended as stages land
NEEDS_APPROVAL: frozenset[int] = frozenset({1, 2})  # guided checkpoints


class _Repo(Protocol):  # structural type for testability
    async def get(self, analysis_id: uuid.UUID) -> Any: ...
    async def set_status(
        self, run: Any, status: str, *, current_stage: int | None = None
    ) -> None: ...
    async def set_stage_result(self, run: Any, stage: int, result: dict[str, Any]) -> None: ...
    async def complete(self, run: Any) -> None: ...
    async def fail(self, run: Any, message: str) -> None: ...


async def execute_run(
    repo: _Repo,
    analysis_id: uuid.UUID,
    runners: dict[int, StageRunner],
    *,
    start_stage: int = 1,
) -> None:
    """Run runnable stages from ``start_stage`` onward, driving the state machine per mode."""
    run = await repo.get(analysis_id)
    if run is None:
        return
    rid = str(analysis_id)[:8]
    for stage in (s for s in RUNNABLE_STAGES if s >= start_stage):
        await repo.set_status(run, state.stage_status(stage, "running"), current_stage=stage)
        result = await runners[stage](run)

        # Stage 1 truly-empty: unconditional hard-stop.
        if stage == 1 and result["count"] == 0:
            logger.warning("run %s: stage 1 found 0 compounds — failing", rid)
            await repo.fail(run, "No compounds found for the selected plants.")
            return

        await repo.set_stage_result(run, stage, result)

        # Stage 2 zero-pass (AD-6): guided -> normal checkpoint; auto -> hard-stop empty-state.
        if stage == 2 and result["count"] == 0:
            if run.mode == "guided":
                logger.info("run %s: stage 2 passed 0 — awaiting approval (guided)", rid)
                await repo.set_status(run, state.stage_status(2, "awaiting_approval"))
                return
            n_in = run.stage_results.get("1", {}).get("count", 0)
            msg = (
                f"0 of {n_in} compounds passed ADME; adjust parameters or enable "
                "skip_adme, then re-run from Step 2."
            )
            logger.warning("run %s: stage 2 passed 0 — failing (auto)", rid)
            await repo.fail(run, msg)
            return

        logger.info("run %s: stage %d done (%d)", rid, stage, result["count"])
        if run.mode == "guided" and stage in NEEDS_APPROVAL:
            await repo.set_status(run, state.stage_status(stage, "awaiting_approval"))
            return

    # auto reached the end of the runnable stages
    last = RUNNABLE_STAGES[-1]
    await repo.set_status(run, state.stage_status(last, "complete"))
    await repo.complete(run)


async def advance_run(repo: _Repo, analysis_id: uuid.UUID, runners: dict[int, StageRunner]) -> None:
    """Guided approval: resume from the stage after ``current_stage``."""
    run = await repo.get(analysis_id)
    if run is None:
        raise ConflictProblem(detail="Run not found.")
    if not state.is_settled(run.status) or not (run.status or "").endswith("_awaiting_approval"):
        raise ConflictProblem(detail="Run is not awaiting approval.")
    current = run.current_stage or 0
    nxt = next((s for s in RUNNABLE_STAGES if s > current), None)
    if nxt is None:
        await repo.set_status(run, state.stage_status(current, "complete"))
        await repo.complete(run)
        return
    await execute_run(repo, analysis_id, runners, start_stage=nxt)


def build_runners(session: Any) -> dict[int, StageRunner]:
    """The single canonical runners map, shared by every engine entry point."""

    async def stage1_runner(run: Any) -> dict[str, Any]:
        plant_ids = [uuid.UUID(p) for p in run.parameters["plant_ids"]]
        manual_ids = [uuid.UUID(c) for c in run.parameters.get("manual_compounds", [])]
        return await stage1.run(session, plant_ids, manual_ids)

    async def stage2_runner(run: Any) -> dict[str, Any]:
        step1 = run.stage_results["1"]["compounds"]
        return await stage2.run(session, step1, run.parameters["adme"])

    return {1: stage1_runner, 2: stage2_runner}


async def run_analysis_task(analysis_id: uuid.UUID) -> None:
    """Background entrypoint: own session, run the engine, commit."""
    async with db.session_scope() as session:
        repo = AnalysisRepository(session)
        runners = build_runners(session)
        await execute_run(repo, analysis_id, runners)
        await session.commit()
