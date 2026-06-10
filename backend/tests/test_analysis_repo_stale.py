"""mark_stages_stale flags only the named, existing stages as stale (jsonb-dirty)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.repositories.analysis import AnalysisRepository


class _FakeSession:
    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_mark_stages_stale_sets_flag_on_existing_only() -> None:
    run = SimpleNamespace(
        stage_results={"1": {"count": 3}, "2": {"count": 3}, "3": {"count": 1}},
        updated_at=None,
    )
    repo = AnalysisRepository(_FakeSession())  # type: ignore[arg-type]

    await repo.mark_stages_stale(run, {2, 3, 9})

    assert run.stage_results["1"].get("stale") is None  # untouched
    assert run.stage_results["2"]["stale"] is True
    assert run.stage_results["3"]["stale"] is True
    assert "9" not in run.stage_results  # not produced -> not created
    assert run.updated_at is not None
