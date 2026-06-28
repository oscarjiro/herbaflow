"""Integration test: fail_stranded bulk-fails only stranded runs.

Seed five analysis_runs with statuses:
  pending, stage_2_running, stage_5_awaiting_approval, complete, failed

Expected: fail_stranded returns 2, flips only the first two to 'failed' with the
message and a bumped updated_at, leaves the other three untouched.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repositories.analysis import AnalysisRepository

REAPER_MESSAGE = "The server restarted while this analysis was running. Please run it again."
# A clearly old timestamp so we can assert updated_at was bumped after the call.
OLD_TS = datetime(2020, 1, 1, tzinfo=UTC)


@pytest_asyncio.fixture()
async def stranded_runs(engine):
    """Seed five runs with known statuses; all have an old updated_at so bumps are detectable."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    ids: dict[str, uuid.UUID] = {
        "pending": uuid.uuid4(),
        "stage_2_running": uuid.uuid4(),
        "stage_5_awaiting_approval": uuid.uuid4(),
        "complete": uuid.uuid4(),
        "failed": uuid.uuid4(),
    }
    async with maker() as s:
        for status, run_id in ids.items():
            await s.execute(
                text(
                    "insert into analysis_runs"
                    "(analysis_id, status, parameters, stage_results, mode, created_at, updated_at)"
                    " values (:id, :status, '{}'::jsonb, '{}'::jsonb, 'guided', :old, :old)"
                ),
                {"id": run_id, "status": status, "old": OLD_TS},
            )
        await s.commit()
    return ids


async def test_fail_stranded_count(engine, stranded_runs) -> None:
    """fail_stranded returns exactly 2 (pending + stage_2_running)."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        n = await AnalysisRepository(session).fail_stranded(message=REAPER_MESSAGE)
        await session.commit()
    assert n == 2


async def test_fail_stranded_flips_only_stranded(engine, stranded_runs) -> None:
    """Pending and stage_2_running flip to failed; the rest stay unchanged."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await AnalysisRepository(session).fail_stranded(message=REAPER_MESSAGE)
        await session.commit()

    STRANDED = {"pending", "stage_2_running"}
    async with maker() as s:
        for status_key, run_id in stranded_runs.items():
            row = (
                await s.execute(
                    text(
                        "select status, error_message, updated_at"
                        " from analysis_runs where analysis_id = :id"
                    ),
                    {"id": run_id},
                )
            ).one()
            if status_key in STRANDED:
                assert row.status == "failed", f"{status_key}: expected failed, got {row.status}"
                assert row.error_message == REAPER_MESSAGE, f"{status_key}: wrong message"
                # updated_at must have been bumped past the seeded OLD_TS (year 2020)
                assert row.updated_at.year > 2020, f"{status_key}: updated_at not bumped"
            else:
                assert row.status == status_key, f"{status_key}: unexpected status {row.status}"
