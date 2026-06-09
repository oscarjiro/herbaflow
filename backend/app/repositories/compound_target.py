"""CompoundTarget repository — the only home for compound→target edge SQL.

Precedence (decided in the service layer): chembl_bioactivity > pubchem_bioassay > stp_import.
``upsert_measured`` overwrites any prior edge for the pair (idempotent re-run). ``insert_stp``
never overwrites an existing pair; STP re-import is a whole-compound delete
(``delete_stp_for_compounds``) then re-insert.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compound_target import CompoundTarget


class CompoundTargetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_measured(self, row: dict[str, Any]) -> None:
        """Insert/overwrite a measured edge (pair grain). Overwrites STP or stale measured edges."""
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

    async def methods_for_pairs(
        self, compound_ids: list[uuid.UUID]
    ) -> dict[tuple[uuid.UUID, uuid.UUID], str | None]:
        """Existing (compound_id, target_id) -> prediction_method for the given compounds."""
        if not compound_ids:
            return {}
        stmt = select(
            CompoundTarget.compound_id, CompoundTarget.target_id, CompoundTarget.prediction_method
        ).where(CompoundTarget.compound_id.in_(compound_ids))
        return {
            (r.compound_id, r.target_id): r.prediction_method
            for r in (await self.session.execute(stmt)).all()
        }

    async def delete_stp_for_compounds(self, compound_ids: list[uuid.UUID]) -> None:
        """Whole-compound replace: drop existing stp_import edges for these compounds."""
        if not compound_ids:
            return
        stmt = delete(CompoundTarget).where(
            CompoundTarget.compound_id.in_(compound_ids),
            CompoundTarget.prediction_method == "stp_import",
        )
        await self.session.execute(stmt)

    async def insert_stp(self, row: dict[str, Any]) -> None:
        """Insert an stp_import edge; no-op if the pair already exists.

        Measured wins — precedence is decided in the service layer.
        """
        stmt = (
            insert(CompoundTarget)
            .values(**row)
            .on_conflict_do_nothing(index_elements=["compound_id", "target_id"])
        )
        await self.session.execute(stmt)

    async def targets_for_compound(self, compound_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(CompoundTarget.target_id).where(CompoundTarget.compound_id == compound_id)
        return [r[0] for r in (await self.session.execute(stmt)).all()]
