"""Integration: analysis_run_progress table — FK cascade on run delete."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.mark.asyncio
async def test_progress_row_cascades_on_run_delete(engine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with maker() as s:
        await s.execute(
            text(
                "insert into analysis_runs"
                "(analysis_id, parameters, status, created_at, updated_at) "
                "values (:r, '{}'::jsonb, 'stage_2_running', now(), now())"
            ),
            {"r": run_id},
        )
        await s.execute(
            text(
                "insert into analysis_run_progress"
                "(analysis_id, stage, processed, total, updated_at) "
                "values (:r, 2, 5, 10, now())"
            ),
            {"r": run_id},
        )
        await s.commit()

    async with maker() as s:
        await s.execute(text("delete from analysis_runs where analysis_id = :r"), {"r": run_id})
        await s.commit()

    async with maker() as s:
        remaining = (
            await s.execute(
                text("select count(*) from analysis_run_progress where analysis_id = :r"),
                {"r": run_id},
            )
        ).scalar_one()
    assert remaining == 0


@pytest.mark.asyncio
async def test_progress_repo_upserts_and_reads(engine) -> None:
    from app.repositories.analysis_progress import AnalysisProgressRepository

    maker = async_sessionmaker(engine, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with maker() as s:
        await s.execute(
            text(
                "insert into analysis_runs"
                "(analysis_id, parameters, status, created_at, updated_at) "
                "values (:r, '{}'::jsonb, 'stage_3_running', now(), now())"
            ),
            {"r": run_id},
        )
        await s.commit()

    async with maker() as s:
        repo = AnalysisProgressRepository(s)
        await repo.upsert(run_id, stage=3, processed=2, total=10)
        await s.commit()
    async with maker() as s:
        repo = AnalysisProgressRepository(s)
        await repo.upsert(run_id, stage=3, processed=7, total=10)
        await s.commit()

    async with maker() as s:
        repo = AnalysisProgressRepository(s)
        row = await repo.get(run_id)
    assert row is not None
    assert (row.stage, row.processed, row.total) == (3, 7, 10)
