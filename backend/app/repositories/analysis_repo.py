from uuid import UUID
from datetime import datetime, timedelta
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.analysis import AnalysisRun


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
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
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
    run.updated_at = datetime.utcnow()
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
    run.updated_at = datetime.utcnow()
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
    run.updated_at = datetime.utcnow()
    if current_stage is not None:
        run.current_stage = current_stage
    if stage_results is not None:
        run.stage_results = {**(run.stage_results or {}), **stage_results}
    if error_message is not None:
        run.error_message = error_message
    if completed:
        run.completed_at = datetime.utcnow()
        run.expires_at = datetime.utcnow() + timedelta(hours=24)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run
