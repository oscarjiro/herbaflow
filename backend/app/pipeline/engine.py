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

from app import contracts, db
from app.errors import ConflictProblem, ValidationProblem
from app.pipeline import edits, state
from app.pipeline.stages import stage1, stage2, stage3, stage4
from app.repositories.analysis import AnalysisRepository

logger = logging.getLogger("herbaflow.pipeline")

StageRunner = Callable[[Any], Awaitable[dict[str, Any]]]


def _empty_stage_message(stage: int, run: Any) -> str:
    """Auto-mode hard-stop message for an entity/gate stage that produced 0 results."""
    if stage == 2:
        n_in = run.stage_results.get("1", {}).get("count", 0)
        return (
            f"0 of {n_in} compounds passed ADME; adjust parameters or enable "
            "skip_adme, then re-run from Step 2."
        )
    if stage == 3:
        return (
            "No targets were identified for the screened compounds; adjust the target "
            "parameters or add a target, then re-run from Step 3."
        )
    if stage == 4:
        return (
            "No disease targets at this score floor; lower min_score or add a target, "
            "then re-run from Step 4."
        )
    return f"Stage {stage} produced no results."


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


async def mark_downstream_stale(repo: _Repo, run: Any, stage: int) -> None:
    """Flag every already-produced stage downstream of ``stage`` as out-of-date.

    A set edit re-derives only the edited stage in place; its heavier downstream stages are
    NOT re-run (D3: recompute only on an explicit reset-from). They keep their stored results,
    flagged stale, until the user confirms with a reset-from. Mode-agnostic.
    """
    produced = {int(k) for k in run.stage_results}
    stale = downstream_closure(stage) & produced
    if stale:
        await repo.mark_stages_stale(run, stale)


# ---------------------------------------------------------------------------
# Stage registry. Extended as stages land in later chunks.
# ---------------------------------------------------------------------------
STAGE_PARAM_GROUP: dict[int, str] = {2: "adme", 3: "target", 4: "disease_targets"}
RUNNABLE_STAGES: tuple[int, ...] = (1, 2, 3, 4)  # extended as stages land
NEEDS_APPROVAL: frozenset[int] = frozenset({1, 2, 3, 4})  # guided checkpoints

# Entity stages carry a user-editable entity set (compounds/targets). Their stored result is
# always run through the durable edit layer so the in-stage add/remove decisions reapply on
# every recompute (E6). Only stage 1 is runnable this chunk; 3 and 4 land in later chunks.
ENTITY_STAGES: frozenset[int] = frozenset({1, 3, 4})

# Per entity stage: (stored list key, id key). The edit layer reapplies on every recompute.
ENTITY_KEYS: dict[int, tuple[str, str]] = {
    1: ("compounds", "compound_id"),
    3: ("targets", "target_id"),
    4: ("targets", "target_id"),
}


class _Repo(Protocol):  # structural type for testability
    async def get(self, analysis_id: uuid.UUID) -> Any: ...
    async def set_status(
        self, run: Any, status: str, *, current_stage: int | None = None
    ) -> None: ...
    async def set_stage_result(self, run: Any, stage: int, result: dict[str, Any]) -> None: ...
    async def clear_stage_results(self, run: Any, stages: set[int]) -> None: ...
    async def mark_stages_stale(self, run: Any, stages: set[int]) -> None: ...
    async def set_parameters(self, run: Any) -> None: ...
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

        # Entity stages: fold the durable edit layer over the freshly-computed entities so
        # in-stage add/remove decisions reapply on every recompute (E6). The stored result
        # becomes the uniform {<list_key>: tagged, computed_ids, count, state} shape.
        if stage in ENTITY_STAGES:
            list_key, id_key = ENTITY_KEYS[stage]
            edit = run.parameters.get("stage_edits", {}).get(str(stage))
            result = {
                **result,
                **edits.build_stage_entities(
                    result[list_key], edit, id_key=id_key, list_key=list_key
                ),
            }

        # Stage 1 truly-empty: unconditional hard-stop (effective forward set is empty).
        if stage == 1 and result["count"] == 0:
            logger.warning("run %s: stage 1 found 0 compounds — failing", rid)
            await repo.fail(run, "No compounds found for the selected plants.")
            return

        await repo.set_stage_result(run, stage, result)

        # Empty downstream entity/gate stage (S2/S3/S4; S1 hard-failed above):
        # guided -> blocking checkpoint (advance is refused); auto -> hard-stop.
        if result["count"] == 0:
            if run.mode == "guided":
                logger.info("run %s: stage %d produced 0 — parking (blocking)", rid, stage)
                await repo.set_status(run, state.stage_status(stage, "awaiting_approval"))
                return
            logger.warning("run %s: stage %d produced 0 — failing (auto)", rid, stage)
            await repo.fail(run, _empty_stage_message(stage, run))
            return

        logger.info("run %s: stage %d done (%d)", rid, stage, result["count"])
        if run.mode == "guided" and stage in NEEDS_APPROVAL:
            await repo.set_status(run, state.stage_status(stage, "awaiting_approval"))
            return

    # auto reached the end of the runnable stages
    last = RUNNABLE_STAGES[-1]
    await repo.set_status(run, state.stage_status(last, "complete"))
    await repo.complete(run)


async def advance_run(
    repo: _Repo,
    analysis_id: uuid.UUID,
    runners: dict[int, StageRunner],
    *,
    defer: bool = False,
) -> int | None:
    """Guided approval: resume from the stage after ``current_stage``.

    Returns the start stage the caller should schedule (``defer=True``) or ``None``
    (nothing left to run, or already executed inline when ``defer=False``).
    """
    run = await repo.get(analysis_id)
    if run is None:
        raise ConflictProblem(detail="Run not found.")
    if not state.is_settled(run.status) or not (run.status or "").endswith("_awaiting_approval"):
        raise ConflictProblem(detail="Run is not awaiting approval.")
    # Any produced stage stale: Step 4 is a parallel root not in the compound chain's closure,
    # so an upstream edit can leave Step 3 stale while Step 4 is current; the any-stale check is
    # branch- and future-proof.
    if any(isinstance(v, dict) and v.get("stale") for v in run.stage_results.values()):
        raise ConflictProblem(
            detail="You have unconfirmed edits — re-run from the edited step before continuing."
        )
    current = run.current_stage or 0
    cur = run.stage_results.get(str(current))
    if cur is not None and cur.get("count", 0) == 0:
        raise ConflictProblem(
            detail=(
                f"Step {current} has no results to carry forward — lower its parameters "
                "and Redo, or add an entry, before continuing."
            )
        )
    nxt = next((s for s in RUNNABLE_STAGES if s > current), None)
    if nxt is None:
        await repo.set_status(run, state.stage_status(current, "complete"))
        await repo.complete(run)
        return None
    if defer:
        # Commit the *_running start state synchronously (closes the double-submit race
        # and makes the running status immediately visible to pollers); the stage runs
        # in a BackgroundTask scheduled by the router.
        await repo.set_status(run, state.stage_status(nxt, "running"), current_stage=nxt)
        return nxt
    await execute_run(repo, analysis_id, runners, start_stage=nxt)
    return None


def _validate_overrides(group: str, overrides: dict[str, Any]) -> None:
    """Validate param overrides against the group's HARD bounds only.

    Enforces ``minimum``/``maximum``/``exclusiveMinimum`` and the JSON-Schema ``type``.
    The advisory ``recommended_min``/``recommended_max`` are NEVER enforced. An unknown key
    or an out-of-range value raises :class:`ValidationProblem` (422).
    """
    bounds = contracts.pipeline_param_bounds(group)
    for name, value in overrides.items():
        spec = bounds.get(name)
        if spec is None:
            raise ValidationProblem(detail=f"Unknown {group} parameter: {name}.")
        kind = spec.get("type")
        if kind == "boolean":
            if not isinstance(value, bool):
                raise ValidationProblem(detail=f"{name} must be a boolean.")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationProblem(detail=f"{name} must be a number.")
        if kind == "integer" and isinstance(value, float) and not value.is_integer():
            raise ValidationProblem(detail=f"{name} must be an integer.")
        minimum = spec.get("minimum")
        if minimum is not None and value < minimum:
            raise ValidationProblem(detail=f"{name} must be >= {minimum}.")
        excl_min = spec.get("exclusiveMinimum")
        if excl_min is not None and value <= excl_min:
            raise ValidationProblem(detail=f"{name} must be > {excl_min}.")
        maximum = spec.get("maximum")
        if maximum is not None and value > maximum:
            raise ValidationProblem(detail=f"{name} must be <= {maximum}.")


async def reset_from(
    repo: _Repo,
    analysis_id: uuid.UUID,
    stage: int,
    runners: dict[int, StageRunner],
    *,
    param_overrides: dict[str, Any] | None = None,
    defer: bool = False,
) -> int | None:
    """Dependency-aware destructive re-run from ``stage``.

    Two modes:

    - **param Redo** (``param_overrides is not None``): inclusive — the edited stage itself is
      recomputed. Overrides are validated against the group's HARD bounds, merged into the frozen
      param group, and the stage + its downstream closure are invalidated. A no-op (overrides equal
      the current group) returns early without clearing or re-running (E7).
    - **set edit** (``param_overrides is None``): exclusive — the edited stage's stored result was
      already updated by the caller; only its downstream closure is invalidated and the re-run
      starts at the nearest runnable dependent (for stage 1 -> stage 2).

    The invalidated stages are cleared BEFORE the re-run (E2), and any re-run failure marks the run
    failed while leaving the cleared downstream cleared (idempotent on outage).

    Returns the start stage the caller should schedule (``defer=True``) or ``None`` (a no-op, no
    runnable dependent, or already executed inline when ``defer=False``). In ``defer`` mode the
    clear + the ``*_running`` start state are committed synchronously and the stage is run in a
    BackgroundTask; the cleared-downstream-stays-cleared invariant still holds because the clear
    is durable before the background run starts.
    """
    run = await repo.get(analysis_id)
    if run is None:
        raise ConflictProblem(detail="Run not found.")

    # E1: only a settled run may be reset.
    if not state.is_settled(run.status):
        raise ConflictProblem(
            detail="Run is still running; wait for it to settle before re-running."
        )

    # Validate the target stage.
    if stage not in RUNNABLE_STAGES:
        raise ValidationProblem(detail=f"Stage {stage} is not runnable.")
    if str(stage) not in run.stage_results:
        raise ValidationProblem(detail=f"Stage {stage} has not been computed yet.")
    if stage > (run.current_stage or 0):
        raise ValidationProblem(detail=f"Stage {stage} is beyond the run's progress.")

    if param_overrides is not None:
        group = STAGE_PARAM_GROUP.get(stage)
        if group is None:
            raise ValidationProblem(detail=f"Stage {stage} takes no parameters.")
        _validate_overrides(group, param_overrides)
        current = dict(run.parameters.get(group, {}))
        merged = {**current, **param_overrides}
        if merged == current:  # E7: nothing changed -> no clear, no re-run.
            return None
        new_params = dict(run.parameters)
        new_params[group] = merged
        run.parameters = new_params
        await repo.set_parameters(run)
        invalidate = {stage} | downstream_closure(stage)
        start = stage
    else:
        invalidate = downstream_closure(stage)
        runnable_dependents = [s for s in DEPENDENTS[stage] if s in RUNNABLE_STAGES]
        if not runnable_dependents:
            # Nothing runnable depends on this stage; clear downstream and settle.
            produced = {int(k) for k in run.stage_results}
            await repo.clear_stage_results(run, invalidate & produced)
            return None
        start = min(runnable_dependents)

    # The explicit re-run confirms any staged edits: drop the reset-from target marker.
    if "rerun_from" in run.parameters:
        params = dict(run.parameters)
        params.pop("rerun_from", None)
        run.parameters = params
        await repo.set_parameters(run)

    # E2: destructive clear of (invalidate ∩ produced) BEFORE re-running.
    produced = {int(k) for k in run.stage_results}
    await repo.clear_stage_results(run, invalidate & produced)

    if defer:
        # Commit the cleared downstream + the *_running start state synchronously; the re-run
        # happens in a BackgroundTask scheduled by the router.
        await repo.set_status(run, state.stage_status(start, "running"), current_stage=start)
        return start

    try:
        await execute_run(repo, analysis_id, runners, start_stage=start)
    except Exception as exc:  # noqa: BLE001 — re-run failure must be idempotent
        await repo.fail(run, f"Re-run from stage {start} failed: {exc}")
    return None


def build_runners(session: Any) -> dict[int, StageRunner]:
    """The single canonical runners map, shared by every engine entry point."""

    async def stage1_runner(run: Any) -> dict[str, Any]:
        plant_ids = [uuid.UUID(p) for p in run.parameters["plant_ids"]]
        manual_ids = [uuid.UUID(c) for c in run.parameters.get("manual_compounds", [])]
        return await stage1.run(session, plant_ids, manual_ids)

    async def stage2_runner(run: Any) -> dict[str, Any]:
        # Screen only the EFFECTIVE S1 set: drop user-removed entries, pass id+name to stage 2.
        effective = [
            {"compound_id": c["compound_id"], "canonical_name": c.get("canonical_name")}
            for c in run.stage_results["1"]["compounds"]
            if c.get("tag") != "user-removed"
        ]
        return await stage2.run(session, effective, run.parameters["adme"])

    async def stage3_runner(run: Any) -> dict[str, Any]:
        passed = run.stage_results["2"]["passed"]
        return await stage3.run(session, passed, run.parameters["target"])

    async def stage4_runner(run: Any) -> dict[str, Any]:
        return await stage4.run(session, run.disease_id, run.parameters["disease_targets"])

    return {1: stage1_runner, 2: stage2_runner, 3: stage3_runner, 4: stage4_runner}


async def run_stages_task(analysis_id: uuid.UUID, start_stage: int = 1) -> None:
    """Background entrypoint: own session, run stages from ``start_stage``, commit.

    Wraps the run in a top-level guard so an uncaught stage error (e.g. a provider
    outage) marks the run ``failed`` instead of leaving it stuck in ``*_running``.
    Used by every scheduling path: create (start_stage=1) and the four mutating
    endpoints (advance / reset-from / edit).
    """
    async with db.session_scope() as session:
        repo = AnalysisRepository(session)
        runners = build_runners(session)
        run = await repo.get(analysis_id)
        if run is None:
            return
        try:
            await execute_run(repo, analysis_id, runners, start_stage=start_stage)
        except Exception as exc:  # noqa: BLE001 — must not leave a stuck *_running status
            await repo.fail(run, f"Stage execution failed: {exc}")
        await session.commit()


async def run_analysis_task(analysis_id: uuid.UUID) -> None:
    """Background entrypoint for ``create``: run the whole pipeline from stage 1."""
    await run_stages_task(analysis_id, 1)
