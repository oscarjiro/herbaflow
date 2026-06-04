from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import CompoundTarget, DiseaseTarget, Target


async def get_target_by_id(session: AsyncSession, target_id: str) -> Target | None:
    result = await session.exec(select(Target).where(Target.target_id == target_id))
    return result.first()


async def get_target_by_gene_symbol(session: AsyncSession, gene_symbol: str) -> Target | None:
    result = await session.exec(
        select(Target).where(Target.gene_symbol == gene_symbol.upper())
    )
    return result.first()


async def get_targets_by_compound(session: AsyncSession, compound_id: str) -> list[Target]:
    stmt = (
        select(Target)
        .join(CompoundTarget, CompoundTarget.target_id == Target.target_id)
        .where(CompoundTarget.compound_id == compound_id)
    )
    result = await session.exec(stmt)
    return list(result.all())


async def get_targets_by_disease(session: AsyncSession, disease_id: str) -> list[Target]:
    stmt = (
        select(Target)
        .join(DiseaseTarget, DiseaseTarget.target_id == Target.target_id)
        .where(DiseaseTarget.disease_id == disease_id)
    )
    result = await session.exec(stmt)
    return list(result.all())


async def upsert_target(session: AsyncSession, target: Target) -> Target:
    existing = await session.exec(
        select(Target).where(Target.canonical_key == target.canonical_key)
    )
    found = existing.first()
    if found:
        return found
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return target
