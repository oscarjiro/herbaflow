from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.analysis import AnalysisRun


def now_utc() -> datetime:
    """Timezone-aware UTC 'now'. Use instead of datetime.utcnow()."""
    return datetime.now(timezone.utc)


async def create_run(
    session: AsyncSession,
    name: str,
    mode: str,
    parameters: dict,
    disease_id: str | None = None,
) -> AnalysisRun:
    run = AnalysisRun(
        analysis_name=name,
        mode=mode,
        parameters=parameters,
        disease_id=disease_id,
        status="pending",
        stage_results={},
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, analysis_id: UUID) -> AnalysisRun | None:
    result = await session.exec(
        select(AnalysisRun).where(AnalysisRun.analysis_id == analysis_id)
    )
    return result.first()


async def get_run_locked(session: AsyncSession, analysis_id: UUID) -> AnalysisRun | None:
    """Fetch the run with a row-level write lock (SELECT ... FOR UPDATE).

    The caller must perform its check-and-write inside the same session/transaction
    so concurrent mutators serialize instead of clobbering each other's JSONB merges.
    """
    result = await session.exec(
        select(AnalysisRun).where(AnalysisRun.analysis_id == analysis_id).with_for_update()
    )
    return result.first()


async def delete_run(session: AsyncSession, analysis_id: UUID) -> None:
    """Delete an analysis run row (used to roll back a create whose manual-input
    injection failed, so no orphan 'pending' run is left behind)."""
    run = await get_run(session, analysis_id)
    if run is not None:
        await session.delete(run)
        await session.commit()


async def list_runs(session: AsyncSession) -> list[AnalysisRun]:
    result = await session.exec(
        select(AnalysisRun).order_by(AnalysisRun.created_at.desc())
    )
    return list(result.all())


async def reset_run_from_stage(
    session: AsyncSession,
    analysis_id: UUID,
    from_stage: int,
    param_overrides: dict | None = None,
) -> AnalysisRun:
    """Clear stage results from from_stage onward and reset status.

    If param_overrides provided, merge into run.parameters before clearing results.
    Dict values are deep-merged; non-dict values are replaced.
    """
    run = await get_run_locked(session, analysis_id)

    # Apply param overrides BEFORE clearing stage results
    if param_overrides:
        merged = dict(run.parameters or {})
        for key, val in param_overrides.items():
            if isinstance(val, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged.get(key, {}), **val}
            else:
                merged[key] = val
        run.parameters = merged

    stage_results = dict(run.stage_results or {})
    for s in range(from_stage, 9):
        stage_results.pop(f"stage_{s}", None)
    run.stage_results = stage_results
    if from_stage == 1:
        run.status = "pending"
        run.current_stage = None
    else:
        run.status = f"stage_{from_stage - 1}_awaiting_approval"
        run.current_stage = from_stage - 1
    run.updated_at = now_utc()
    run.completed_at = None
    run.expires_at = None
    run.error_message = None
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def merge_run_parameters(
    session: AsyncSession,
    analysis_id: UUID,
    param_overrides: dict,
) -> None:
    """Deep-merge param_overrides into run.parameters without clearing stage results.

    Used by approve_stage to pre-configure the next stage before it runs.
    Dict values are deep-merged; non-dict values are replaced.
    """
    run = await get_run_locked(session, analysis_id)
    merged = dict(run.parameters or {})
    for key, val in param_overrides.items():
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged.get(key, {}), **val}
        else:
            merged[key] = val
    run.parameters = merged
    run.updated_at = now_utc()
    session.add(run)
    await session.commit()


async def update_run_status(
    session: AsyncSession,
    analysis_id: UUID,
    status: str,
    current_stage: int | None = None,
    stage_results: dict | None = None,
    error_message: str | None = None,
    completed: bool = False,
) -> AnalysisRun:
    run = await get_run_locked(session, analysis_id)
    run.status = status
    run.updated_at = now_utc()
    if current_stage is not None:
        run.current_stage = current_stage
    if stage_results is not None:
        run.stage_results = {**(run.stage_results or {}), **stage_results}
    if error_message is not None:
        run.error_message = error_message
    if completed:
        run.completed_at = now_utc()
        run.expires_at = now_utc() + timedelta(hours=24)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def merge_stage_results_locked(
    session: AsyncSession,
    analysis_id: UUID,
    mutate: Callable[[dict], dict],
    status: str | None = None,
) -> AnalysisRun | None:
    """Atomically read-modify-write stage_results under a row-level write lock.

    Acquires SELECT ... FOR UPDATE on the run, passes a copy of the CURRENT
    stage_results to ``mutate``, stores the dict ``mutate`` returns, optionally
    updates status, and commits — so the whole read-modify-write is serialized
    against concurrent mutators (closes the lost-update race on the JSONB blob).

    Any rows already staged on ``session`` (e.g. Target / CompoundTarget upserts)
    are committed together with the stage_results change in this one transaction.
    Returns None if the run no longer exists.
    """
    run = await get_run_locked(session, analysis_id)
    if run is None:
        return None
    current = dict(run.stage_results or {})
    run.stage_results = mutate(current)
    if status is not None:
        run.status = status
    run.updated_at = now_utc()
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def touch_heartbeat(session: AsyncSession, analysis_id: UUID) -> None:
    """Bump updated_at to now — the liveness heartbeat written periodically while a
    stage is executing. Lightweight: no status/stage_results change."""
    run = await get_run(session, analysis_id)
    if run is None:
        return
    run.updated_at = now_utc()
    session.add(run)
    await session.commit()


TIMEOUT_MESSAGE = "Run timed out or was interrupted; please retry."


def _is_in_progress_status(status: str) -> bool:
    return status == "pending" or status.endswith("_running")


async def reap_stale_runs(session: AsyncSession, threshold_seconds: int) -> int:
    """Mark in-progress runs whose updated_at is older than threshold as failed
    (failure_kind=timeout). Idempotent; safe to run from multiple workers."""
    cutoff = now_utc() - timedelta(seconds=threshold_seconds)
    result = await session.exec(
        select(AnalysisRun).where(
            or_(
                AnalysisRun.status == "pending",
                AnalysisRun.status.like("stage_%_running"),
            )
        )
    )
    reaped = 0
    for run in result.all():
        # updated_at is timestamptz (tz-aware on read); compare aware to aware.
        updated_at = run.updated_at if run.updated_at else datetime.min.replace(tzinfo=timezone.utc)
        if updated_at >= cutoff:
            continue
        run.status = "failed"
        run.error_message = TIMEOUT_MESSAGE
        run.stage_results = {**(run.stage_results or {}), "_run_health": {"failure_kind": "timeout"}}
        run.updated_at = now_utc()
        session.add(run)
        reaped += 1
    if reaped:
        await session.commit()
    return reaped


async def mark_failed_if_stale(
    session: AsyncSession, analysis_id: UUID, threshold_seconds: int
) -> AnalysisRun | None:
    """If the run is in-progress and its updated_at is past threshold, mark it
    failed (timeout) under a row lock and return it; otherwise return the run as-is.
    Used by get_analysis for instant cleanup of a watched zombie."""
    run = await get_run_locked(session, analysis_id)
    if run is None:
        return None
    if not _is_in_progress_status(run.status):
        return run
    cutoff = now_utc() - timedelta(seconds=threshold_seconds)
    updated_at = run.updated_at if run.updated_at else datetime.min.replace(tzinfo=timezone.utc)
    if updated_at >= cutoff:
        return run
    run.status = "failed"
    run.error_message = TIMEOUT_MESSAGE
    run.stage_results = {**(run.stage_results or {}), "_run_health": {"failure_kind": "timeout"}}
    run.updated_at = now_utc()
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run
