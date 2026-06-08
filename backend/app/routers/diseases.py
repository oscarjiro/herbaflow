"""Disease HTTP surface."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.disease import DiseaseRead
from app.services.disease import DiseaseService

router = APIRouter(tags=["diseases"])


@router.get("/diseases", response_model=list[DiseaseRead])
async def list_diseases(session: AsyncSession = Depends(get_session)) -> list[DiseaseRead]:
    return await DiseaseService(session).list_all()
