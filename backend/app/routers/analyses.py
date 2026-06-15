"""Analysis run HTTP surface."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.pipeline.engine import run_analysis_task, run_stages_task
from app.schemas.analysis import AnalysisCreate, AnalysisRead, ResetFromRequest, StageEditRequest
from app.services.analysis import AnalysisService

router = APIRouter(tags=["analyses"])


async def _commit(session: AsyncSession) -> None:
    await session.commit()


@router.post("/analyses", response_model=AnalysisRead, status_code=202)
async def create_analysis(
    payload: AnalysisCreate,
    background: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> AnalysisRead:
    run, replayed = await AnalysisService.from_session(session).create(
        payload, idempotency_key=idempotency_key
    )
    await _commit(session)
    if not replayed:
        background.add_task(run_analysis_task, run.analysis_id)
    return run


@router.get("/analyses/{analysis_id}", response_model=AnalysisRead)
async def get_analysis(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> AnalysisRead:
    return await AnalysisService.from_session(session).get(analysis_id)


@router.post("/analyses/{analysis_id}/advance", response_model=AnalysisRead, status_code=202)
async def advance_analysis(
    analysis_id: uuid.UUID,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> AnalysisRead:
    service = AnalysisService.from_session(session)
    start = await service.advance(analysis_id, defer=True)
    await _commit(session)
    if start is not None:
        background.add_task(run_stages_task, analysis_id, start)
    return await service.get(analysis_id)


@router.post(
    "/analyses/{analysis_id}/reset-from/{stage}", response_model=AnalysisRead, status_code=202
)
async def reset_from(
    analysis_id: uuid.UUID,
    stage: int,
    payload: ResetFromRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> AnalysisRead:
    service = AnalysisService.from_session(session)
    overrides = payload.parameters.get(str(stage)) if payload.parameters else None
    run_set = await service.reset_from(analysis_id, stage, overrides, defer=True)
    await _commit(session)
    if run_set:
        background.add_task(run_stages_task, analysis_id, min(run_set), run_set)
    return await service.get(analysis_id)


@router.delete("/analyses/{analysis_id}", status_code=204)
async def delete_analysis(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    await AnalysisService.from_session(session).delete(analysis_id)
    await _commit(session)


@router.post(
    "/analyses/{analysis_id}/stages/{stage}/edit", response_model=AnalysisRead, status_code=202
)
async def edit_stage(
    analysis_id: uuid.UUID,
    stage: int,
    payload: StageEditRequest,
    session: AsyncSession = Depends(get_session),
) -> AnalysisRead:
    service = AnalysisService.from_session(session)
    await service.edit_stage(analysis_id, stage, add=payload.add, remove=payload.remove)
    await _commit(session)
    return await service.get(analysis_id)
