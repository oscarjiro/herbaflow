from collections import defaultdict

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import PlantAlias


async def get_aliases_by_plant_ids(
    session: AsyncSession, plant_ids: list[str]
) -> dict[str, list[str]]:
    """Return a mapping of plant_id → list[alias_name] for the given IDs."""
    if not plant_ids:
        return {}
    result = await session.exec(
        select(PlantAlias).where(PlantAlias.plant_id.in_(plant_ids))
    )
    aliases: dict[str, list[str]] = defaultdict(list)
    for alias in result.all():
        aliases[alias.plant_id].append(alias.alias_name)
    return dict(aliases)
