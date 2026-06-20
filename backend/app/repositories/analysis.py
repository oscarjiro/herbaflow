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
        idempotency_key: str | None = None,
        disease_id: uuid.UUID | None,
        plant_ids: list[uuid.UUID],
        mode: str,
        pipeline_parameters: dict[str, Any] | None = None,
        extra_parameters: dict[str, Any] | None = None,
        stage_edits: dict[str, Any] | None = None,
        stage_results: dict[str, Any] | None = None,
        current_stage: int | None = None,
    ) -> AnalysisRun:
        run = AnalysisRun(
            analysis_name=analysis_name,
            idempotency_key=idempotency_key,
            disease_id=disease_id,
            parameters={
                "plant_ids": [str(p) for p in plant_ids],
                "stage_edits": stage_edits or {},
                **(extra_parameters or {}),
                **(pipeline_parameters or {}),
            },
            status="pending",
            stage_results=stage_results or {},
            mode=mode,
            current_stage=current_stage,
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

    async def list_recent(self, *, limit: int, offset: int) -> list[AnalysisRun]:
        result = await self.session.execute(
            select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_idempotency_key(self, key: str) -> AnalysisRun | None:
        result = await self.session.execute(
            select(AnalysisRun).where(AnalysisRun.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def rollback(self) -> None:
        """Roll back the current transaction (used to recover after a unique-key clash)."""
        await self.session.rollback()

    async def delete(self, run: AnalysisRun) -> None:
        await self.session.delete(run)
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

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

    async def clear_stage_results(self, run: AnalysisRun, stages: set[int]) -> None:
        """Drop the stored results for ``stages`` (jsonb dirty via dict reassign)."""
        merged = {k: v for k, v in run.stage_results.items() if int(k) not in stages}
        run.stage_results = merged
        run.updated_at = now_utc()
        await self.session.flush()

    async def mark_stages_stale(self, run: AnalysisRun, stages: set[int]) -> None:
        """Flag stored results for ``stages`` as out-of-date (jsonb dirty via dict reassign).

        Only already-produced stages are touched; a stage with no stored result is skipped.
        """
        merged = dict(run.stage_results)
        for s in stages:
            key = str(s)
            if key in merged:
                merged[key] = {**merged[key], "stale": True}
        run.stage_results = merged
        run.updated_at = now_utc()
        await self.session.flush()

    async def set_parameters(self, run: AnalysisRun) -> None:
        """Flush a re-assigned ``run.parameters`` dict (jsonb dirty)."""
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
