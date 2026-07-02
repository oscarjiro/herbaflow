"""Target repository — the only home for target SQL."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.target import Target


class TargetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, target_id: uuid.UUID) -> Target | None:
        stmt = select(Target).where(Target.target_id == target_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_gene_symbol(self, gene_symbol: str) -> Target | None:
        """Return the single stored human target for this exact gene symbol, or None.

        Returns None when there is no row OR more than one row (ambiguous) so the caller
        falls back to the authoritative UniProt lookup. Identity stays canonicalized on the
        primary accession; this is a DB-first cache for the symbol->accession hop only.
        """
        stmt = select(Target).where(Target.gene_symbol == gene_symbol).limit(2)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows[0] if len(rows) == 1 else None

    async def upsert(self, row: dict[str, Any]) -> None:
        stmt = insert(Target).values(**row).on_conflict_do_nothing(index_elements=["target_id"])
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

    async def count(self) -> int:
        return int((await self.session.execute(select(func.count(Target.target_id)))).scalar_one())
