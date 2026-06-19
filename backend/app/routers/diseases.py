"""Disease HTTP surface."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.disease import DiseaseRead
from app.services.disease import DiseaseService

router = APIRouter(tags=["diseases"])


@router.get("/diseases", response_model=list[DiseaseRead])
async def list_diseases(
    q: str | None = Query(default=None, description="Search term (canonical name or alias)"),
    limit: int = Query(default=50, ge=1, description="Maximum number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    session: AsyncSession = Depends(get_session),
) -> list[DiseaseRead]:
    return await DiseaseService(session).search(q, limit=limit, offset=offset)
