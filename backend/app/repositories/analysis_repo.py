from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.analysis import AnalysisRun


async def create_run(
    session: AsyncSession,
    name: str,
    mode: str,
    parameters: dict,
) -> AnalysisRun:
    run = AnalysisRun(
        analysis_id=uuid4(),
        analysis_name=name,
        mode=mode,
        parameters=parameters,
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


async def list_runs(session: AsyncSession) -> list[AnalysisRun]:
    result = await session.exec(
        select(AnalysisRun).order_by(AnalysisRun.created_at.desc())
    )
    return list(result.all())


async def update_run_status(
    session: AsyncSession,
    analysis_id: UUID,
    status: str,
    current_stage: int | None = None,
    stage_results: dict | None = None,
    error_message: str | None = None,
    completed: bool = False,
) -> AnalysisRun:
    run = await get_run(session, analysis_id)
    run.status = status
    run.updated_at = datetime.utcnow()
    if current_stage is not None:
        run.current_stage = current_stage
    if stage_results is not None:
        existing = run.stage_results or {}
        existing.update(stage_results)
        run.stage_results = existing
    if error_message is not None:
        run.error_message = error_message
    if completed:
        run.completed_at = datetime.utcnow()
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run
