"""Compound repository — the only home for compound SQL."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compound import Compound
from app.services.descriptors import MolDescriptors


class CompoundRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, compound_id: uuid.UUID) -> Compound | None:
        stmt = select(Compound).where(Compound.compound_id == compound_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert(self, row: dict[str, Any]) -> None:
        stmt = insert(Compound).values(**row).on_conflict_do_nothing(index_elements=["compound_id"])
        await self.session.execute(stmt)

    async def existing_ids(self, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not ids:
            return set()
        stmt = select(Compound.compound_id).where(Compound.compound_id.in_(ids))
        return {r[0] for r in (await self.session.execute(stmt)).all()}

    async def get_many(self, ids: list[uuid.UUID]) -> list[Compound]:
        if not ids:
            return []
        stmt = select(Compound).where(Compound.compound_id.in_(ids))
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_descriptors(self, compound_id: uuid.UUID, d: MolDescriptors) -> None:
        """Persist RDKit-computed descriptors back to the compound row.

        Idempotent: calling again with updated values overwrites the previous ones.
        No commit here — the caller's session_scope commits.
        """
        stmt = (
            update(Compound)
            .where(Compound.compound_id == compound_id)
            .values(
                molecular_weight=d.molecular_weight,
                logp=d.logp,
                hbond_donors=d.hbond_donors,
                hbond_acceptors=d.hbond_acceptors,
                tpsa=d.tpsa,
                rotatable_bonds=d.rotatable_bonds,
                np_likeness_score=d.np_likeness_score,
                num_ro5_violations=d.num_ro5_violations,
                is_pains_positive=d.is_pains_positive,
            )
        )
        await self.session.execute(stmt)

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Compound.compound_id)))
        return int(result.scalar_one())
