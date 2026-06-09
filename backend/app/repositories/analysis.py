"""Analysis run data access."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import now_utc
from app.models.analysis_run import AnalysisRun


def expires_after(completed_at: datetime) -> datetime:
    """Runs expire 24h after completion."""
    return completed_at + timedelta(hours=24)


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        analysis_name: str | None,
        disease_id: uuid.UUID,
        plant_ids: list[uuid.UUID],
        mode: str,
        manual_compound_ids: list[uuid.UUID],
        pipeline_parameters: dict[str, Any] | None = None,
    ) -> AnalysisRun:
        run = AnalysisRun(
            analysis_name=analysis_name,
            disease_id=disease_id,
            parameters={
                "plant_ids": [str(p) for p in plant_ids],
                "manual_compounds": [str(c) for c in manual_compound_ids],
                "stage_edits": {},
                **(pipeline_parameters or {}),
            },
            status="pending",
            stage_results={},
            mode=mode,
            current_stage=None,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get(self, analysis_id: uuid.UUID) -> AnalysisRun | None:
        result = await self.session.execute(
            select(AnalysisRun).where(AnalysisRun.analysis_id == analysis_id)
        )
        return result.scalar_one_or_none()

    async def set_status(
        self, run: AnalysisRun, status: str, *, current_stage: int | None = None
    ) -> None:
        run.status = status
        if current_stage is not None:
            run.current_stage = current_stage
        run.updated_at = now_utc()
        await self.session.flush()

    async def set_stage_result(self, run: AnalysisRun, stage: int, result: dict[str, Any]) -> None:
        merged = dict(run.stage_results)
        merged[str(stage)] = result
        run.stage_results = merged
        run.updated_at = now_utc()
        await self.session.flush()

    async def complete(self, run: AnalysisRun) -> None:
        done = now_utc()
        run.status = "complete"
        run.completed_at = done
        run.expires_at = expires_after(done)
        run.updated_at = done
        await self.session.flush()

    async def fail(self, run: AnalysisRun, message: str) -> None:
        run.status = "failed"
        run.error_message = message
        run.updated_at = now_utc()
        await self.session.flush()
