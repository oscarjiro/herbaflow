"""Plant read service."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.plant import PlantRepository
from app.schemas.plant import PlantRead


class PlantService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PlantRepository(session)

    async def list_all(self) -> list[PlantRead]:
        rows = await self.repo.list_all()
        return [PlantRead.model_validate(r) for r in rows]
