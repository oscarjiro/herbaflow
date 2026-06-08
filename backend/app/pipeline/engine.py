"""Run orchestration: drive a run through the state machine and Stage 1."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app import db
from app.errors import ConflictProblem
from app.pipeline import state
from app.pipeline.stages import stage1
from app.repositories.analysis import AnalysisRepository

StageRunner = Callable[[Any], Awaitable[dict[str, Any]]]

# Phase 2 has one stage; advancing the last stage completes the run.
_LAST_STAGE = 1


class _Repo(Protocol):  # structural type for testability
    async def get(self, analysis_id: uuid.UUID) -> Any: ...
    async def set_status(
        self, run: Any, status: str, *, current_stage: int | None = None
    ) -> None: ...
    async def set_stage_result(self, run: Any, stage: int, result: dict[str, Any]) -> None: ...
    async def complete(self, run: Any) -> None: ...
    async def fail(self, run: Any, message: str) -> None: ...


async def execute_run(repo: _Repo, analysis_id: uuid.UUID, stage_runner: StageRunner) -> None:
    """Run Stage 1 and advance the state machine per mode."""
    run = await repo.get(analysis_id)
    if run is None:
        return
    await repo.set_status(run, state.stage_status(1, "starting"), current_stage=1)
    await repo.set_status(run, state.stage_status(1, "running"))
    result = await stage_runner(run)
    if result["count"] == 0:
        await repo.fail(run, "No compounds found for the selected plants.")
        return
    await repo.set_stage_result(run, 1, result)
    if run.mode == "guided":
        await repo.set_status(run, state.stage_status(1, "awaiting_approval"))
        return
    await repo.set_status(run, state.stage_status(1, "complete"))
    await repo.complete(run)


async def advance_run(repo: _Repo, analysis_id: uuid.UUID) -> None:
    """Guided approval: advance from awaiting_approval. With one stage, completes the run."""
    run = await repo.get(analysis_id)
    if run is None:
        raise ConflictProblem(detail="Run not found.")
    if run.status != state.stage_status(1, "awaiting_approval"):
        raise ConflictProblem(detail="Run is not awaiting approval.")
    await repo.set_status(run, state.stage_status(_LAST_STAGE, "complete"))
    await repo.complete(run)


async def run_analysis_task(analysis_id: uuid.UUID) -> None:
    """Background entrypoint: own session, run the engine, commit."""
    async with db.session_scope() as session:
        repo = AnalysisRepository(session)

        async def stage_runner(run: Any) -> dict[str, Any]:
            plant_ids = [uuid.UUID(p) for p in run.parameters["plant_ids"]]
            return await stage1.run(session, plant_ids)

        await execute_run(repo, analysis_id, stage_runner)
        await session.commit()
