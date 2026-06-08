"""Plant HTTP surface."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.plant import PlantRead
from app.services.plant import PlantService

router = APIRouter(tags=["plants"])


@router.get("/plants", response_model=list[PlantRead])
async def list_plants(session: AsyncSession = Depends(get_session)) -> list[PlantRead]:
    return await PlantService(session).list_all()
