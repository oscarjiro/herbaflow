"""Analysis run HTTP surface."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.pipeline.engine import run_analysis_task
from app.schemas.analysis import AnalysisCreate, AnalysisRead
from app.services.analysis import AnalysisService

router = APIRouter(tags=["analyses"])


async def _commit(session: AsyncSession) -> None:
    await session.commit()


@router.post("/analyses", response_model=AnalysisRead, status_code=202)
async def create_analysis(
    payload: AnalysisCreate,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> AnalysisRead:
    run = await AnalysisService.from_session(session).create(payload)
    await _commit(session)
    background.add_task(run_analysis_task, run.analysis_id)
    return run


@router.get("/analyses/{analysis_id}", response_model=AnalysisRead)
async def get_analysis(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> AnalysisRead:
    return await AnalysisService.from_session(session).get(analysis_id)


@router.post("/analyses/{analysis_id}/advance", response_model=AnalysisRead)
async def advance_analysis(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> AnalysisRead:
    service = AnalysisService.from_session(session)
    await service.advance(analysis_id)
    await _commit(session)
    return await service.get(analysis_id)
