"""Compound repository — the only home for compound SQL."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compound import Compound
from app.models.source_system import SourceSystem


class CompoundRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_key(self, canonical_key: str) -> Compound | None:
        stmt = select(Compound).where(Compound.canonical_key == canonical_key)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert(self, row: dict[str, Any]) -> None:
        stmt = (
            insert(Compound).values(**row).on_conflict_do_nothing(index_elements=["canonical_key"])
        )
        await self.session.execute(stmt)

    async def existing_ids(self, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not ids:
            return set()
        stmt = select(Compound.compound_id).where(Compound.compound_id.in_(ids))
        return {r[0] for r in (await self.session.execute(stmt)).all()}

    async def manual_source_id(self) -> uuid.UUID | None:
        stmt = select(SourceSystem.source_id).where(SourceSystem.source_name == "Manual Entry")
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Compound.compound_id)))
        return int(result.scalar_one())
