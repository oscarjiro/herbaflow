"""Target repository — the only home for target SQL."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_system import SourceSystem
from app.models.target import Target


class TargetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_key(self, canonical_key: str) -> Target | None:
        stmt = select(Target).where(Target.canonical_key == canonical_key)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert(self, row: dict[str, Any]) -> None:
        stmt = insert(Target).values(**row).on_conflict_do_nothing(index_elements=["canonical_key"])
        await self.session.execute(stmt)

    async def existing_ids(self, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not ids:
            return set()
        stmt = select(Target.target_id).where(Target.target_id.in_(ids))
        return {r[0] for r in (await self.session.execute(stmt)).all()}

    async def get_many(self, ids: list[uuid.UUID]) -> list[Target]:
        if not ids:
            return []
        stmt = select(Target).where(Target.target_id.in_(ids))
        return list((await self.session.execute(stmt)).scalars().all())

    async def source_id_by_name(self, name: str) -> uuid.UUID | None:
        stmt = select(SourceSystem.source_id).where(SourceSystem.source_name == name)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count(self) -> int:
        return int((await self.session.execute(select(func.count(Target.target_id)))).scalar_one())
