from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.repositories import compound_repo
from app.schemas.compound import CompoundResponse

router = APIRouter(prefix="/compounds", tags=["compounds"])


@router.get("", response_model=list[CompoundResponse])
async def list_compounds(
    limit: int = Query(100, le=500),
    offset: int = 0,
    has_smiles: bool | None = None,
    has_chembl: bool | None = None,
    session: AsyncSession = Depends(get_session),
):
    compounds = await compound_repo.list_compounds(
        session, limit=limit, offset=offset, has_smiles=has_smiles, has_chembl=has_chembl
    )
    return [CompoundResponse(**c.model_dump()) for c in compounds]


@router.get("/{compound_id}", response_model=CompoundResponse)
async def get_compound(compound_id: str, session: AsyncSession = Depends(get_session)):
    try:
        UUID(compound_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Compound not found")
    compound = await compound_repo.get_compound_by_id(session, compound_id)
    if not compound:
        raise HTTPException(status_code=404, detail="Compound not found")
    return CompoundResponse(**compound.model_dump())
