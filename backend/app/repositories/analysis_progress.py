"""Data access for per-run live progress."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import now_utc
from app.models.analysis_run_progress import AnalysisRunProgress


class AnalysisProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self, analysis_id: uuid.UUID, *, stage: int, processed: int, total: int
    ) -> None:
        stmt = pg_insert(AnalysisRunProgress).values(
            analysis_id=analysis_id,
            stage=stage,
            processed=processed,
            total=total,
            updated_at=now_utc(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AnalysisRunProgress.analysis_id],
            set_={
                "stage": stmt.excluded.stage,
                "processed": stmt.excluded.processed,
                "total": stmt.excluded.total,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get(self, analysis_id: uuid.UUID) -> AnalysisRunProgress | None:
        result = await self.session.execute(
            select(AnalysisRunProgress).where(AnalysisRunProgress.analysis_id == analysis_id)
        )
        return result.scalar_one_or_none()
