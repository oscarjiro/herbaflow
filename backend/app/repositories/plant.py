"""Plant data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plant import Plant, PlantAlias
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
        """Return raw candidate (plant, matched_alias | None) rows for ranking.

        ``q`` is already stripped by the caller.  Empty ``q`` returns all plants
        ordered by canonical name, each paired with ``None``.  Non-empty ``q``
        executes two queries:
        - canonical name ILIKE %q% (alias=None)
        - alias_name ILIKE %q% (alias=alias_name)
        and merges them in Python (data set is small: ~478 plants / ~556 aliases).
        Uses SQLAlchemy ``.ilike()`` with a bound pattern — never string-formats ``q``.
        The term's ``%``/``_`` are escaped (``like_escape``) so they match literally
        instead of acting as LIKE wildcards.
        """
        if not q:
            rows = await self.session.execute(
                select(Plant).order_by(Plant.canonical_scientific_name)
            )
            return [(p, None) for p in rows.scalars().all()]

        pattern = f"%{like_escape(q)}%"

        # Canonical-name hits
        canon_result = await self.session.execute(
            select(Plant).where(Plant.canonical_scientific_name.ilike(pattern, escape="\\"))
        )
        canon_rows: list[tuple[Plant, str | None]] = [
            (p, None) for p in canon_result.scalars().all()
        ]

        # Alias-name hits (join alias table to the parent plant)
        alias_result = await self.session.execute(
            select(Plant, PlantAlias.alias_name)
            .join(PlantAlias, PlantAlias.plant_id == Plant.plant_id)
            .where(PlantAlias.alias_name.ilike(pattern, escape="\\"))
        )
        alias_rows: list[tuple[Plant, str | None]] = [
            (plant, alias_name) for plant, alias_name in alias_result.all()
        ]

        return canon_rows + alias_rows
