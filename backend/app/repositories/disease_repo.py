from collections import defaultdict

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Disease, DiseaseAlias, DiseaseTarget, Target


async def get_aliases_by_disease_ids(
    session: AsyncSession, disease_ids: list[str]
) -> dict[str, list[str]]:
    """Return a mapping of disease_id → list[alias_name] for the given IDs."""
    if not disease_ids:
        return {}
    result = await session.exec(
        select(DiseaseAlias).where(DiseaseAlias.disease_id.in_(disease_ids))
    )
    aliases: dict[str, list[str]] = defaultdict(list)
    for alias in result.all():
        aliases[alias.disease_id].append(alias.alias_name)
    return dict(aliases)


async def get_disease_by_id(session: AsyncSession, disease_id: str) -> Disease | None:
    result = await session.exec(select(Disease).where(Disease.disease_id == disease_id))
    return result.first()


async def list_diseases(session: AsyncSession) -> list[Disease]:
    result = await session.exec(select(Disease).order_by(Disease.disease_name))
    return list(result.all())


async def get_disease_by_ontology_id(session: AsyncSession, ontology_id: str) -> Disease | None:
    result = await session.exec(
        select(Disease).where(Disease.ontology_id == ontology_id)
    )
    return result.first()


async def get_targets_for_disease(
    session: AsyncSession,
    disease_id: str,
    min_score: float = 0.3,
) -> list[tuple]:
    stmt = (
        select(Target, DiseaseTarget.score)
        .join(DiseaseTarget, DiseaseTarget.target_id == Target.target_id)
        .where(DiseaseTarget.disease_id == disease_id)
        .where(DiseaseTarget.score >= min_score)
        .order_by(DiseaseTarget.score.desc())
    )
    result = await session.exec(stmt)
    return list(result.all())
