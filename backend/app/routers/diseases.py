import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.repositories import disease_repo
from app.schemas.disease import DiseaseResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diseases", tags=["diseases"])


@router.get("", response_model=list[DiseaseResponse])
async def list_diseases(session: AsyncSession = Depends(get_session)):
    diseases = await disease_repo.list_diseases(session)
    disease_ids = [d.disease_id for d in diseases]
    counts = await disease_repo.count_targets_per_disease_bulk(session, disease_ids)
    try:
        aliases = await disease_repo.get_aliases_by_disease_ids(session, disease_ids)
    except Exception as e:
        logger.warning("alias fetch failed: %s", e)
        aliases = {}
    return [
        DiseaseResponse(
            **d.model_dump(),
            disease_aliases=aliases.get(d.disease_id, []),
            target_count=counts.get(d.disease_id, 0),
        )
        for d in diseases
    ]


@router.get("/{disease_id}", response_model=DiseaseResponse)
async def get_disease(disease_id: str, session: AsyncSession = Depends(get_session)):
    try:
        UUID(disease_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Disease not found")
    disease = await disease_repo.get_disease_by_id(session, disease_id)
    if not disease:
        raise HTTPException(status_code=404, detail="Disease not found")
    counts = await disease_repo.count_targets_per_disease_bulk(session, [disease_id])
    try:
        aliases = await disease_repo.get_aliases_by_disease_ids(session, [disease_id])
    except Exception as e:
        logger.warning("alias fetch failed: %s", e)
        aliases = {}
    return DiseaseResponse(
        **disease.model_dump(),
        disease_aliases=aliases.get(disease_id, []),
        target_count=counts.get(disease_id, 0),
    )
