"""mark_downstream_stale flags the produced downstream closure of a stage."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.pipeline import engine


class _FakeRepo:
    def __init__(self) -> None:
        self.marked: set[int] = set()

    async def mark_stages_stale(self, run, stages: set[int]) -> None:
        self.marked |= stages
        for s in stages:
            run.stage_results[str(s)]["stale"] = True


@pytest.mark.asyncio
async def test_marks_only_produced_downstream() -> None:
    # Produced 1,2,3; edit stage 1 -> downstream closure {2,3,5,6,7,8} ∩ produced = {2,3}.
    run = SimpleNamespace(stage_results={"1": {}, "2": {}, "3": {}})
    repo = _FakeRepo()
    await engine.mark_downstream_stale(repo, run, 1)
    assert repo.marked == {2, 3}


@pytest.mark.asyncio
async def test_no_produced_downstream_marks_nothing() -> None:
    # Parked at stage 1; nothing downstream produced -> nothing marked.
    run = SimpleNamespace(stage_results={"1": {}})
    repo = _FakeRepo()
    await engine.mark_downstream_stale(repo, run, 1)
    assert repo.marked == set()
