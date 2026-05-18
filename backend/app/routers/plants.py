from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.schemas.plant import PlantResponse
from app.schemas.compound import CompoundResponse
from app.repositories import compound_repo
from app.models.plant import Plant

router = APIRouter(prefix="/plants", tags=["plants"])


@router.get("", response_model=list[PlantResponse])
async def list_plants(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Plant).order_by(Plant.canonical_scientific_name))
    plants = result.all()
    if not plants:
        return []
    plant_ids = [p.plant_id for p in plants]
    counts = await compound_repo.count_compounds_per_plant_bulk(session, plant_ids)
    return [
        PlantResponse(
            plant_id=p.plant_id,
            canonical_scientific_name=p.canonical_scientific_name,
            family_name=p.family_name,
            compound_count=counts.get(p.plant_id, 0),
        )
        for p in plants
    ]


@router.get("/{plant_id}", response_model=PlantResponse)
async def get_plant(plant_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Plant).where(Plant.plant_id == plant_id))
    plant = result.first()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    count = await compound_repo.count_compounds_for_plant(session, plant_id)
    return PlantResponse(
        plant_id=plant.plant_id,
        canonical_scientific_name=plant.canonical_scientific_name,
        family_name=plant.family_name,
        compound_count=count,
    )


@router.get("/{plant_id}/compounds", response_model=list[CompoundResponse])
async def get_plant_compounds(plant_id: str, session: AsyncSession = Depends(get_session)):
    compounds = await compound_repo.get_compounds_by_plant(session, plant_id)
    return [CompoundResponse(**c.model_dump()) for c in compounds]
