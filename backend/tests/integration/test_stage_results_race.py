"""Concurrency proof for the locked stage_results read-modify-write primitive.

Two concurrent writers each append a distinct item to the same stage_results
key. Without a row lock the second write clobbers the first (lost update);
with merge_stage_results_locked both survive. All writes are run-scoped
(one analysis_runs row) and cleaned up by the created_runs fixture.
"""
import asyncio
from uuid import UUID

import pytest
from app.database import async_session_factory
from app.models.analysis import AnalysisRun
from app.repositories import analysis_repo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_run() -> UUID:
    from datetime import datetime, timezone
    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)
        run = AnalysisRun(
            analysis_name="RACE_TEST merge primitive",
            mode="guided",
            parameters={},
            status="stage_3_awaiting_approval",
            stage_results={"stage_3": {"items": []}},
            created_at=now,
            updated_at=now,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run.analysis_id


async def _append_item(analysis_id: UUID, item: str) -> None:
    def mutate(current: dict) -> dict:
        stage = dict(current.get("stage_3") or {})
        items = list(stage.get("items") or [])
        items.append(item)
        stage["items"] = items
        return {**current, "stage_3": stage}

    async with async_session_factory() as session:
        await analysis_repo.merge_stage_results_locked(session, analysis_id, mutate)


def _append_mutate(item: str):
    def mutate(current: dict) -> dict:
        stage = dict(current.get("stage_3") or {})
        items = list(stage.get("items") or [])
        items.append(item)
        stage["items"] = items
        return {**current, "stage_3": stage}

    return mutate


async def test_concurrent_merge_keeps_both_writes(created_runs):
    """Smoke check: two gathered merges leave both writes present. NOTE this
    alone does not PROVE the lock is required — in this environment the pool /
    event-loop scheduling tends to serialize the two writers even without a
    lock, so it passes either way. test_locked_merge_blocks_concurrent_writer
    below is the deterministic proof that the FOR UPDATE lock is doing the work.
    """
    analysis_id = await _seed_run()
    created_runs.append(analysis_id)

    await asyncio.gather(
        _append_item(analysis_id, "A"),
        _append_item(analysis_id, "B"),
    )

    async with async_session_factory() as session:
        run = await analysis_repo.get_run(session, analysis_id)
    items = run.stage_results["stage_3"]["items"]
    assert set(items) == {"A", "B"}, f"lost update: {items}"


async def test_locked_merge_blocks_concurrent_writer(created_runs):
    """Deterministic proof that merge_stage_results_locked serializes writers.

    Transaction 1 holds the row's FOR UPDATE lock. A second concurrent merge must
    BLOCK until transaction 1 commits, then re-read and preserve both writes. A
    plain (unlocked) read would NOT block a FOR UPDATE holder in Postgres, so the
    `assert not writer2.done()` line fails if the primitive's lock is removed —
    making this a real falsifier (unlike the gathered-timing smoke above).
    """
    analysis_id = await _seed_run()
    created_runs.append(analysis_id)

    # Transaction 1 acquires and holds the row write lock (mimics an in-flight merge).
    holder = async_session_factory()
    session1 = await holder.__aenter__()
    writer2 = None
    try:
        run1 = await analysis_repo.get_run_locked(session1, analysis_id)

        async def _writer2():
            async with async_session_factory() as session2:
                await analysis_repo.merge_stage_results_locked(
                    session2, analysis_id, _append_mutate("B")
                )

        writer2 = asyncio.create_task(_writer2())
        await asyncio.sleep(0.75)
        assert not writer2.done(), (
            "writer 2 was not blocked — merge_stage_results_locked is not holding "
            "a row lock (a plain SELECT does not block a FOR UPDATE holder)"
        )

        # Transaction 1 appends its own item and commits, releasing the lock.
        run1.stage_results = _append_mutate("A")(dict(run1.stage_results or {}))
        session1.add(run1)
        await session1.commit()
    finally:
        await holder.__aexit__(None, None, None)
        if writer2 is not None:
            # Unblocks once the lock is released; bounded so a hang can't wedge CI.
            await asyncio.wait_for(writer2, timeout=10)

    async with async_session_factory() as session:
        run = await analysis_repo.get_run(session, analysis_id)
    items = run.stage_results["stage_3"]["items"]
    assert set(items) == {"A", "B"}, f"lost update: {items}"
