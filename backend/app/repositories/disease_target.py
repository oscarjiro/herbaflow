"""DiseaseTarget repository — the only home for disease-target SQL (Stage 4 read + count).

Step 4 is a filtered DB read of the ETL-seeded snapshot (no live Open Targets call). The read
joins the seeded ``targets`` rows so the view has the gene symbol / UniProt accession / source
link alongside the association score. NULL scores are excluded by ``score >= min_score`` (SQL
NULL comparison is never true).
"""

from __future__ import annotations

import uuid
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
                DiseaseTarget.score,
                DiseaseTarget.association_type,
            )
            .join(Target, Target.target_id == DiseaseTarget.target_id)
            .where(
                DiseaseTarget.disease_id == disease_id,
                DiseaseTarget.score >= min_score,
            )
            .order_by(DiseaseTarget.score.desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "target_id": str(r.target_id),
                "gene_symbol": r.gene_symbol,
                "uniprot_accession": r.uniprot_accession,
                "source_url": r.source_url,
                "score": r.score,
                "association_type": r.association_type,
            }
            for r in rows
        ]

    async def count_for_disease(self, disease_id: uuid.UUID, min_score: float) -> int:
        """Count of seeded disease-targets with ``score >= min_score`` (setup-form glyph;
        entry-modes consumes)."""
        stmt = select(func.count(DiseaseTarget.disease_target_id)).where(
            DiseaseTarget.disease_id == disease_id,
            DiseaseTarget.score >= min_score,
        )
        return int((await self.session.execute(stmt)).scalar_one())
