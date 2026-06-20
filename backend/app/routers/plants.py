"""Plant HTTP surface."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.plant import PlantRead
from app.services.plant import PlantService

router = APIRouter(tags=["plants"])


@router.get("/plants", response_model=list[PlantRead])
async def list_plants(
    q: str | None = Query(default=None, description="Search term (canonical name or alias)"),
    limit: int = Query(default=50, ge=1, description="Maximum number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    session: AsyncSession = Depends(get_session),
) -> list[PlantRead]:
    return await PlantService(session).search(q, limit=limit, offset=offset)
