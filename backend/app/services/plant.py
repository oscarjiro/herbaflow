"""Plant read service."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.plant import PlantRepository
from app.schemas.plant import PlantRead
from app.services.alias_search import rank_and_page_search

logger = logging.getLogger("herbaflow.plants")


class PlantService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PlantRepository(session)

    async def list_all(self) -> list[PlantRead]:
        rows = await self.repo.list_all()
        return [PlantRead.model_validate(r) for r in rows]

    async def search(
        self,
        q: str | None,
        *,
        limit: int,
        offset: int,
    ) -> list[PlantRead]:
        """Search plants by canonical name or alias, ranked and paged.

        Empty/absent ``q`` returns the full list ordered by canonical name.
        An unknown term returns an empty list (200 []).
        """
        term = (q or "").strip().lower()
        rows = await self.repo.search_candidates(q=term)

        ranked = rank_and_page_search(
            rows,
            term,
            name_of=lambda plant: plant.canonical_scientific_name,
            id_of=lambda plant: plant.plant_id,
            limit=limit,
            offset=offset,
        )
        reads = []
        for plant, matched_alias in ranked:
            read = PlantRead.model_validate(plant)
            read.matched_alias = matched_alias
            reads.append((read, plant.plant_id))

        counts = await self.repo.compound_counts([pid for _, pid in reads])
        for read, pid in reads:
            read.compound_count = counts.get(pid, 0)
        result = [read for read, _ in reads]
        logger.info("plant search q=%r count=%d", q, len(result))
        return result
