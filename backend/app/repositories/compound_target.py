"""CompoundTarget repository — the only home for compound→target edge SQL.

Edges are *measured* only. Precedence (decided in the service layer):
``chembl_bioactivity > pubchem_bioassay``. ``upsert_measured`` overwrites any prior edge for
the pair (idempotent re-run). User-asserted targets (manual add / SwissTargetPrediction
paste-back) are run-scoped (the run's Stage-3 set) and are never written as canonical edges.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compound_target import CompoundTarget


class CompoundTargetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_measured(self, row: dict[str, Any]) -> None:
        """Insert/overwrite a measured edge (pair grain). Idempotent on re-run."""
        stmt = (
            insert(CompoundTarget)
            .values(**row)
            .on_conflict_do_update(
                index_elements=["compound_id", "target_id"],
                set_={
                    "prediction_method": row["prediction_method"],
                    "score": row.get("score"),
                    "pchembl_value": row.get("pchembl_value"),
                    "source_id": row.get("source_id"),
                    "source_url": row.get("source_url"),
                    "retrieved_at": row.get("retrieved_at"),
                },
            )
        )
        await self.session.execute(stmt)

    async def targets_for_compound(self, compound_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(CompoundTarget.target_id).where(CompoundTarget.compound_id == compound_id)
        return [r[0] for r in (await self.session.execute(stmt)).all()]
