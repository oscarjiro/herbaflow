"""DiseaseTarget repository — the only home for disease-target SQL (Stage 4 read + count).

Step 4 is a filtered DB read of the ETL-seeded snapshot (no live Open Targets call). The read
joins the seeded ``targets`` rows so the view has the gene symbol / UniProt accession / source
link alongside the Open Targets association score. NULL scores are excluded by
``opentargets_score >= min_score`` (SQL NULL comparison is never true).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disease_target import DiseaseTarget
from app.models.target import Target


class DiseaseTargetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def targets_for_disease(
        self, disease_id: uuid.UUID, min_score: float
    ) -> list[dict[str, Any]]:
        """Seeded disease-targets with ``score >= min_score``, ordered by score desc,
        joined to ``targets``."""
        stmt = (
            select(
                Target.target_id,
                Target.gene_symbol,
                Target.uniprot_accession,
                Target.source_url,
                DiseaseTarget.opentargets_score,
                DiseaseTarget.association_type,
            )
            .join(Target, Target.target_id == DiseaseTarget.target_id)
            .where(
                DiseaseTarget.disease_id == disease_id,
                DiseaseTarget.opentargets_score >= min_score,
            )
            .order_by(DiseaseTarget.opentargets_score.desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "target_id": str(r.target_id),
                "gene_symbol": r.gene_symbol,
                "uniprot_accession": r.uniprot_accession,
                "source_url": r.source_url,
                "opentargets_score": r.opentargets_score,
                "association_type": r.association_type,
            }
            for r in rows
        ]

    async def count_for_disease(self, disease_id: uuid.UUID, min_score: float) -> int:
        """Count of seeded disease-targets with ``score >= min_score`` (setup-form glyph;
        entry-modes consumes)."""
        stmt = select(func.count(DiseaseTarget.disease_target_id)).where(
            DiseaseTarget.disease_id == disease_id,
            DiseaseTarget.opentargets_score >= min_score,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def target_counts(self, disease_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Distinct **total** (unfiltered) disease-target count per disease (catalog display).

        Distinct from ``count_for_disease`` (single id, score-filtered, run-time). This is the
        unfiltered catalog scale shown on search rows / selected cards.
        """
        if not disease_ids:
            return {}
        stmt = (
            select(
                DiseaseTarget.disease_id,
                func.count(func.distinct(DiseaseTarget.target_id)),
            )
            .where(DiseaseTarget.disease_id.in_(disease_ids))
            .group_by(DiseaseTarget.disease_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}
