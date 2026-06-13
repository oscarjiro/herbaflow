"""Results-handoff export endpoints (HTTP only). Assembles nothing itself — delegates to
``app.services.export``; lets ConflictProblem (409, not complete) / NotFoundProblem (404)
propagate to the global problem+json handler."""

from __future__ import annotations

import io
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.export import assemble_export

router = APIRouter(tags=["export"])


def _disposition(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("/analyses/{analysis_id}/export")
async def export_bundle(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    artifacts = await assemble_export(session, analysis_id)
    data = artifacts.bundle()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers=_disposition(f"herbaflow-{analysis_id}.zip"),
    )


@router.get("/analyses/{analysis_id}/export/ctp-nodes.csv")
async def export_ctp_nodes(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    a = await assemble_export(session, analysis_id)
    return Response(a.ctp_nodes, media_type="text/csv", headers=_disposition("ctp-nodes.csv"))


@router.get("/analyses/{analysis_id}/export/ctp-edges.csv")
async def export_ctp_edges(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    a = await assemble_export(session, analysis_id)
    return Response(a.ctp_edges, media_type="text/csv", headers=_disposition("ctp-edges.csv"))


@router.get("/analyses/{analysis_id}/export/docking.csv")
async def export_docking(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    a = await assemble_export(session, analysis_id)
    return Response(a.docking, media_type="text/csv", headers=_disposition("docking.csv"))


@router.get("/analyses/{analysis_id}/export/report")
async def export_report(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    a = await assemble_export(session, analysis_id)
    return Response(a.report, media_type="text/markdown", headers=_disposition("report.md"))
