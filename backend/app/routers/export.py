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
from app.services.export import ExportArtifacts, assemble_export

router = APIRouter(tags=["export"])


def _disposition(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


def _require_compounds(a: ExportArtifacts) -> None:
    if not a.has_compounds:
        raise NotFoundProblem(
            "compound-target-pathway and docking exports are not available for a target-only run"
        )


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
    return Response(
        a.report, media_type="text/markdown", headers=_disposition(f"{a.slug}_report.md")
    )


@router.get("/analyses/{analysis_id}/export/network-and-docking.zip")
async def export_network(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    a = await assemble_export(session, analysis_id)
    _require_compounds(a)
    return _zip_response(a.network_bundle(), f"{a.slug}_network-and-docking.zip")


@router.get("/analyses/{analysis_id}/export/stages.zip")
async def export_stages(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    a = await assemble_export(session, analysis_id)
    return _zip_response(a.stages_bundle(), f"{a.slug}_stages.zip")


@router.get("/analyses/{analysis_id}/export/all-results.zip")
async def export_all(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    a = await assemble_export(session, analysis_id)
    return _zip_response(a.all_results_bundle(), f"{a.slug}_all-results.zip")


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
    _require_compounds(a)
    return Response(a.ctp_nodes, media_type="text/csv", headers=_disposition("ctp-nodes.csv"))


@router.get("/analyses/{analysis_id}/export/ctp-edges.csv")
async def export_ctp_edges(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    a = await assemble_export(session, analysis_id)
    _require_compounds(a)
    return Response(a.ctp_edges, media_type="text/csv", headers=_disposition("ctp-edges.csv"))


@router.get("/analyses/{analysis_id}/export/docking.csv")
async def export_docking(
    analysis_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    a = await assemble_export(session, analysis_id)
    _require_compounds(a)
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
async def export_artifact(
    analysis_id: uuid.UUID, filename: str, session: AsyncSession = Depends(get_session)
) -> Response:
    """One artifact by its deterministic filename — serves both the per-stage/graph CSVs (e.g.
    ``stage5_overlap.csv``) and the rendered chart PNGs (e.g. ``ctp-network.png``,
    ``stage5_venn.png``). The set of valid filenames is the assembled network+stage allowlist — an
    unknown artifact, or a chart that could not be drawn (None, conditional-PNG rule), 404s, so the
    path segment can never address an arbitrary file (Software §8). Declared last, so the explicit
    ``.zip`` / ``.md`` / ``.csv`` routes above still win."""
    a = await assemble_export(session, analysis_id)
    artifact = {**a._network_files(), **a._stage_files()}.get(filename)
    if isinstance(artifact, bytes):
        return Response(artifact, media_type="image/png", headers=_disposition(filename))
    if isinstance(artifact, str):
        return Response(artifact, media_type="text/csv", headers=_disposition(filename))
    raise NotFoundProblem(f"unknown export artifact {filename!r}")
