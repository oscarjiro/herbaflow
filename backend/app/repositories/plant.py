"""Plant data access."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plant import Plant
from app.models.plant_compound import PlantCompound
from app.services.alias_search import like_escape


class PlantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Plant]:
        result = await self.session.execute(select(Plant).order_by(Plant.canonical_scientific_name))
        return list(result.scalars().all())

    async def missing_ids(self, plant_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        """Return the subset of plant_ids that do not exist."""
        result = await self.session.execute(
            select(Plant.plant_id).where(Plant.plant_id.in_(plant_ids))
        )
        present = {row[0] for row in result.all()}
        return [pid for pid in plant_ids if pid not in present]

    async def search_candidates(self, q: str) -> list[tuple[Plant, str | None]]:
        """Return raw candidate (plant, None) rows for ranking.

        ``q`` is already stripped by the caller. Empty ``q`` returns all plants ordered by
        canonical name. Non-empty ``q`` matches the canonical scientific name (ILIKE %q%);
        synonym/alias search was retired with the alias tables (the frontend filters a locally
        cached catalog, so ``matched_alias`` is always ``None``). Uses a bound ``.ilike()``
        pattern — never string-formats ``q`` — with the term's ``%``/``_`` escaped
        (``like_escape``) so they match literally instead of acting as LIKE wildcards.
        """
        if not q:
            rows = await self.session.execute(
                select(Plant).order_by(Plant.canonical_scientific_name)
            )
            return [(p, None) for p in rows.scalars().all()]

        pattern = f"%{like_escape(q)}%"
        canon_result = await self.session.execute(
            select(Plant).where(Plant.canonical_scientific_name.ilike(pattern, escape="\\"))
        )
        return [(p, None) for p in canon_result.scalars().all()]

    async def compound_counts(self, plant_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Distinct compound count per plant for the given ids (catalog display).

        ``plant_compounds`` enforces uniqueness on the ``(plant_id, compound_id)`` pair, so
        COUNT(DISTINCT compound_id) is a harmless extra guard rather than a fix for a real
        uniqueness gap. Plants with no compounds are absent from the result; callers default to 0.
        """
        if not plant_ids:
            return {}
        stmt = (
            select(
                PlantCompound.plant_id,
                func.count(func.distinct(PlantCompound.compound_id)),
            )
            .where(PlantCompound.plant_id.in_(plant_ids))
            .group_by(PlantCompound.plant_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}
