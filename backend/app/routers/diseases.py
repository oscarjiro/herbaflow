import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.schemas.disease import DiseaseResponse
from app.repositories import disease_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diseases", tags=["diseases"])


@router.get("", response_model=list[DiseaseResponse])
async def list_diseases(session: AsyncSession = Depends(get_session)):
    diseases = await disease_repo.list_diseases(session)
    try:
        aliases = await disease_repo.get_aliases_by_disease_ids(
            session, [d.disease_id for d in diseases]
        )
    except Exception as e:
        logger.warning("alias fetch failed: %s", e)
        aliases = {}
    return [
        DiseaseResponse(**d.model_dump(), disease_aliases=aliases.get(d.disease_id, []))
        for d in diseases
    ]


@router.get("/{disease_id}", response_model=DiseaseResponse)
async def get_disease(disease_id: str, session: AsyncSession = Depends(get_session)):
    disease = await disease_repo.get_disease_by_id(session, disease_id)
    if not disease:
        raise HTTPException(status_code=404, detail="Disease not found")
    try:
        aliases = await disease_repo.get_aliases_by_disease_ids(session, [disease_id])
    except Exception as e:
        logger.warning("alias fetch failed: %s", e)
        aliases = {}
    return DiseaseResponse(
        **disease.model_dump(), disease_aliases=aliases.get(disease_id, [])
    )
