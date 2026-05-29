from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import Compound, PlantCompound


async def get_compound_by_id(session: AsyncSession, compound_id: str) -> Compound | None:
    result = await session.exec(select(Compound).where(Compound.compound_id == compound_id))
    return result.first()


async def get_compounds_by_plant(session: AsyncSession, plant_id: str) -> list[Compound]:
    stmt = (
        select(Compound)
        .join(PlantCompound, PlantCompound.compound_id == Compound.compound_id)
        .where(PlantCompound.plant_id == plant_id)
    )
    result = await session.exec(stmt)
    return list(result.all())


async def list_compounds(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    has_smiles: bool | None = None,
    has_chembl: bool | None = None,
) -> list[Compound]:
    stmt = select(Compound)
    if has_smiles is True:
        stmt = stmt.where(Compound.smiles.is_not(None))
    elif has_smiles is False:
        stmt = stmt.where(Compound.smiles.is_(None))
    if has_chembl is True:
        stmt = stmt.where(Compound.chembl_id.is_not(None))
    elif has_chembl is False:
        stmt = stmt.where(Compound.chembl_id.is_(None))
    stmt = stmt.offset(offset).limit(limit)
    result = await session.exec(stmt)
    return list(result.all())


async def get_compounds_by_ids(session: AsyncSession, compound_ids: list[str]) -> list[Compound]:
    result = await session.exec(
        select(Compound).where(Compound.compound_id.in_(compound_ids))
    )
    return list(result.all())


async def count_compounds_for_plant(session: AsyncSession, plant_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(PlantCompound)
        .where(PlantCompound.plant_id == plant_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def count_compounds_per_plant_bulk(session: AsyncSession, plant_ids: list[str]) -> dict[str, int]:
    if not plant_ids:
        return {}
    stmt = (
        select(PlantCompound.plant_id, func.count().label("cnt"))
        .where(PlantCompound.plant_id.in_(plant_ids))
        .group_by(PlantCompound.plant_id)
    )
    result = await session.execute(stmt)
    return {row.plant_id: row.cnt for row in result.all()}


async def get_compounds_for_plants(session: AsyncSession, plant_ids: list[str]) -> list[Compound]:
    if not plant_ids:
        return []
    stmt = (
        select(Compound)
        .join(PlantCompound, PlantCompound.compound_id == Compound.compound_id)
        .where(PlantCompound.plant_id.in_(plant_ids))
        .distinct()
    )
    result = await session.exec(stmt)
    return list(result.all())
