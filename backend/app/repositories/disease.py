"""Disease data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disease import Disease


class DiseaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Disease]:
        result = await self.session.execute(select(Disease).order_by(Disease.disease_name))
        return list(result.scalars().all())

    async def exists(self, disease_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Disease.disease_id).where(Disease.disease_id == disease_id)
        )
        return result.first() is not None
