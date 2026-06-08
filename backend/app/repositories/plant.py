"""Plant data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plant import Plant


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
