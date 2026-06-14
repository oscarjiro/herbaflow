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
from app.errors import NotFoundProblem
from app.services.export import assemble_export

router = APIRouter(tags=["export"])


def _disposition(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


def _zip_response(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data), media_type="application/zip", headers=_disposition(filename)
    )


# ---------------------------------------------------------------------------
# Bundles
# ---------------------------------------------------------------------------


@router.get("/analyses/{analysis_id}/export/report.md")
async def export_report(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    a = await assemble_export(session, analysis_id)
    return Response(a.report, media_type="text/markdown", headers=_disposition("report.md"))


@router.get("/analyses/{analysis_id}/export/network-and-docking.zip")
async def export_network(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    a = await assemble_export(session, analysis_id)
    return _zip_response(a.network_bundle(), "network-and-docking.zip")


@router.get("/analyses/{analysis_id}/export/stages.zip")
async def export_stages(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    a = await assemble_export(session, analysis_id)
    return _zip_response(a.stages_bundle(), "stages.zip")


@router.get("/analyses/{analysis_id}/export/all-results.zip")
async def export_all(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    a = await assemble_export(session, analysis_id)
    return _zip_response(a.all_results_bundle(), f"herbaflow-{analysis_id}.zip")


# ---------------------------------------------------------------------------
# Per-artifact CSVs (backing individual downloads). Graph CSVs map to their artifact
# field directly; the per-stage CSVs are looked up by deterministic filename in the
# assembled stage-files set (an allowlist that guards path-injection — Software §8).
# ---------------------------------------------------------------------------


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


@router.get("/analyses/{analysis_id}/export/stage6_ppi_nodes.csv")
async def export_ppi_nodes(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    a = await assemble_export(session, analysis_id)
    return Response(
        a.ppi_nodes, media_type="text/csv", headers=_disposition("stage6_ppi_nodes.csv")
    )


@router.get("/analyses/{analysis_id}/export/{filename}")
async def export_stage_csv(
    analysis_id: uuid.UUID, filename: str, session: AsyncSession = Depends(get_session)
) -> Response:
    """One per-stage CSV by its deterministic filename (e.g. ``stage5_overlap.csv``). The set of
    valid filenames is the assembled stage-files allowlist — an unknown/None artifact 404s, so the
    path segment can never address an arbitrary file (Software §8)."""
    a = await assemble_export(session, analysis_id)
    artifact = a._stage_files().get(filename)
    if not isinstance(artifact, str):
        raise NotFoundProblem(f"unknown export artifact {filename!r}")
    return Response(artifact, media_type="text/csv", headers=_disposition(filename))
