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
                "insert into analysis_runs(analysis_id, parameters, status, updated_at) "
                "values (:r, '{}'::jsonb, 'stage_2_running', now())"
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
