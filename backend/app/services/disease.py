"""Disease read service."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.disease import DiseaseRepository
from app.schemas.disease import DiseaseRead


class DiseaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = DiseaseRepository(session)

    async def list_all(self) -> list[DiseaseRead]:
        rows = await self.repo.list_all()
        return [DiseaseRead.model_validate(r) for r in rows]
