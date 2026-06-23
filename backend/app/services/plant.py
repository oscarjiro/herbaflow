"""Plant read service."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Hashable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plant import Plant
from app.repositories.plant import PlantRepository
from app.schemas.plant import PlantRead
from app.services.alias_search import merge_candidates, rank_match

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

        if not term:
            # Empty query: rows already ordered by canonical name; just page.
            paged = rows[offset : offset + limit]
            reads = [(PlantRead.model_validate(plant), plant.plant_id) for plant, _ in paged]
        else:
            # Build flat candidate list: (plant_id, rank, matched_alias | None)
            candidates: list[tuple[Hashable, int, str | None]] = []
            for plant, alias in rows:
                r = rank_match(term, canonical=plant.canonical_scientific_name)
                if r is not None:
                    candidates.append((plant.plant_id, r, None))
                    continue
                r = rank_match(term, alias=alias)
                if r is not None:
                    candidates.append((plant.plant_id, r, alias))

            merged = merge_candidates(candidates)

            # Map back to Plant objects for the response; sort ties by canonical name.
            plant_by_id: dict[uuid.UUID, Plant] = {plant.plant_id: plant for plant, _ in rows}

            def sort_key(row: tuple[Hashable, int, str | None]) -> tuple[int, str]:
                key, rank, _alias = row
                plant = plant_by_id[key]  # type: ignore[index]
                name = (plant.canonical_scientific_name or "").lower()
                return (rank, name)

            merged.sort(key=sort_key)
            page: list[tuple[Hashable, int, str | None]] = merged[offset : offset + limit]

            reads = []
            for plant_id, _rank, matched_alias in page:
                plant = plant_by_id[plant_id]  # type: ignore[index]
                read = PlantRead.model_validate(plant)
                read.matched_alias = matched_alias
                reads.append((read, plant.plant_id))

        counts = await self.repo.compound_counts([pid for _, pid in reads])
        for read, pid in reads:
            read.compound_count = counts.get(pid, 0)
        result = [read for read, _ in reads]
        logger.info("plant search q=%r count=%d", q, len(result))
        return result
