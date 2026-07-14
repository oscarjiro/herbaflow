"""Analysis run HTTP surface."""

from __future__ import annotations

import base64
import binascii
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import NotFoundProblem
from app.pipeline.engine import run_analysis_task, run_stages_task
from app.repositories.analysis import AnalysisRepository
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisListItem,
    AnalysisRead,
    ResetFromRequest,
    StageEditRequest,
)
from app.security import RATE_LIMIT_CREATE, limiter
from app.services.analysis import AnalysisService

router = APIRouter(tags=["analyses"])


async def _commit(session: AsyncSession) -> None:
    await session.commit()


@router.post("/analyses", response_model=AnalysisRead, status_code=202)
@limiter.limit(RATE_LIMIT_CREATE)
async def create_analysis(
    request: Request,
    payload: AnalysisCreate,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> AnalysisRead:
    run = await AnalysisService.from_session(session).create(payload)
    await _commit(session)
    background.add_task(run_analysis_task, run.analysis_id)
    return run


@router.get("/analyses", response_model=list[AnalysisListItem])
async def list_analyses(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[AnalysisListItem]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return await AnalysisService.from_session(session).list_recent(limit=limit, offset=offset)


@router.get("/analyses/{analysis_id}", response_model=AnalysisRead)
async def get_analysis(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> AnalysisRead:
    return await AnalysisService.from_session(session).get(analysis_id)


@router.get("/analyses/{analysis_id}/stage6-image.png")
async def get_stage6_image(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """Serve the stored STRING PPI network PNG as soon as Stage 6 has produced it.

    Unlike the results export (complete-run only, 409 otherwise), this reads the base64 image
    persisted at ``stage_results["6"].network_image`` directly off the run, so the frontend can
    offer the download the moment Stage 6 finishes mid-run. 404 when the run is missing or the
    image is absent (STRING's image fetch is supplementary and degrades to None). The complete-run
    export bundle keeps its own matplotlib fallback for a genuinely missing STRING image."""
    run = await AnalysisRepository(session).get(analysis_id)
    if run is None:
        raise NotFoundProblem(f"analysis {analysis_id} not found")
    encoded = ((run.stage_results or {}).get("6") or {}).get("network_image")
    if not encoded:
        raise NotFoundProblem(f"analysis {analysis_id} has no Stage 6 network image")
    try:
        image = base64.b64decode(encoded)
    except (ValueError, binascii.Error) as exc:
        raise NotFoundProblem(f"analysis {analysis_id} has no Stage 6 network image") from exc
    return Response(
        image,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="stage6_ppi_network.png"'},
    )


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
    await service.edit_stage(
        analysis_id,
        stage,
        add=payload.add,
        remove=payload.remove,
        stp_compound_id=payload.stp_compound_id,
        stp_target_ids=payload.stp_target_ids,
    )
    await _commit(session)
    return await service.get(analysis_id)
