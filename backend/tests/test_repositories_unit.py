from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.clock import now_utc
from app.repositories.analysis import AnalysisRepository, expires_after


def test_expires_after_is_24h() -> None:
    base = now_utc()
    assert expires_after(base) == base + timedelta(hours=24)


class _FakeSession:
    def __init__(self) -> None:
        self.flushed = 0

    async def flush(self) -> None:
        self.flushed += 1


@pytest.mark.asyncio
async def test_clear_stage_results_drops_only_named_stages() -> None:
    session = _FakeSession()
    repo = AnalysisRepository(session)  # type: ignore[arg-type]
    run = SimpleNamespace(
        stage_results={"1": {"count": 5}, "2": {"count": 3}},
        updated_at=None,
    )

    await repo.clear_stage_results(run, {2})

    assert "2" not in run.stage_results
    assert run.stage_results == {"1": {"count": 5}}
    assert run.updated_at is not None
    assert session.flushed == 1


@pytest.mark.asyncio
async def test_clear_stage_results_reassigns_dict_for_jsonb_dirty() -> None:
    # The new dict must be a distinct object (jsonb dirty-tracking), not a mutated in place.
    session = _FakeSession()
    repo = AnalysisRepository(session)  # type: ignore[arg-type]
    original = {"1": {"count": 1}, "2": {"count": 2}}
    run = SimpleNamespace(stage_results=original, updated_at=None)

    await repo.clear_stage_results(run, {1, 2})

    assert run.stage_results == {}
    assert run.stage_results is not original
