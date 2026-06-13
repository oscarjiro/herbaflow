"""CompoundTarget repository — the only home for compound→target edge SQL.

Edges are *measured* only. Precedence (``chembl_bioactivity > pubchem_bioassay``) is decided in
the service layer (Stage 3) before the rows reach ``replace_for_compound``. User-asserted targets
(manual add / SwissTargetPrediction paste-back) are run-scoped (the run's Stage-3 set) and are
never written as canonical edges.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compound_target import CompoundTarget


class CompoundTargetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def edges_for_compound(self, compound_id: uuid.UUID) -> list[dict[str, Any]]:
        """A compound's measured edges joined to targets, shaped like stage3's in-memory edges.

        Carries the discovery params so the caller can decide reuse vs refetch (D9). The Target
        model has no ``canonical_name`` column, so the caller derives the display name the same way
        ``compute`` does (gene_symbol -> uniprot_accession -> target_id) — one shaping path.
        """
        from app.models.target import Target

        stmt = (
            select(
                CompoundTarget.target_id,
                CompoundTarget.prediction_method,
                CompoundTarget.pchembl_value,
                CompoundTarget.score,
                CompoundTarget.source_url,
                CompoundTarget.min_pchembl,
                CompoundTarget.min_assay_confidence,
                Target.gene_symbol,
                Target.uniprot_accession,
            )
            .join(Target, Target.target_id == CompoundTarget.target_id)
            .where(CompoundTarget.compound_id == compound_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "target_id": str(r.target_id),
                "prediction_method": r.prediction_method,
                "pchembl_value": r.pchembl_value,
                "score": r.score,
                "source_url": r.source_url,
                "min_pchembl": r.min_pchembl,
                "min_assay_confidence": r.min_assay_confidence,
                "gene_symbol": r.gene_symbol,
                "uniprot_accession": r.uniprot_accession,
            }
            for r in rows
        ]

    async def replace_for_compound(
        self, compound_id: uuid.UUID, rows: list[dict[str, Any]]
    ) -> None:
        """Delete the compound's existing edges, then insert the fresh set (D9 — keeps one
        discovery-param pair per compound and drops stale below-threshold edges)."""
        from app.services import canonical

        await self.session.execute(
            delete(CompoundTarget).where(CompoundTarget.compound_id == compound_id)
        )
        for row in rows:
            tid = row["target_id"]
            self.session.add(
                CompoundTarget(
                    compound_target_id=uuid.UUID(
                        canonical.compound_target_id(str(compound_id), str(tid))
                    ),
                    compound_id=compound_id,
                    target_id=uuid.UUID(str(tid)),
                    prediction_method=row["prediction_method"],
                    score=row.get("score"),
                    pchembl_value=row.get("pchembl_value"),
                    source_id=row.get("source_id"),
                    source_url=row.get("source_url"),
                    retrieved_at=row.get("retrieved_at"),
                    min_pchembl=row.get("min_pchembl"),
                    min_assay_confidence=row.get("min_assay_confidence"),
                )
            )
