"""Unit tests for the throttled, best-effort ProgressReporter."""

from __future__ import annotations

import contextlib
import uuid

import pytest

from app.pipeline.progress import ProgressReporter


class _FakeRepo:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, int]] = []

    async def upsert(self, analysis_id, *, stage, processed, total) -> None:
        self.calls.append((stage, processed, total))


def _scope_factory(repo, *, raises: bool = False):
    @contextlib.asynccontextmanager
    async def scope():
        if raises:
            raise RuntimeError("db down")
        yield _Session(repo)
        # committed implicitly by the reporter

    class _Session:
        def __init__(self, repo):
            self._repo = repo

        async def commit(self) -> None:
            pass

    return scope


@pytest.mark.asyncio
async def test_first_update_writes_then_throttles(monkeypatch) -> None:
    repo = _FakeRepo()
    t = {"now": 0.0}
    rid = uuid.uuid4()
    reporter = ProgressReporter(
        rid,
        repo_factory=lambda session: repo,
        session_scope=_scope_factory(repo),
        min_interval=1.0,
        clock=lambda: t["now"],
    )
    await reporter.update(2, 1, 10)  # first write always lands
    await reporter.update(2, 2, 10)  # within interval -> throttled
    assert repo.calls == [(2, 1, 10)]
    t["now"] = 1.5
    await reporter.update(2, 3, 10)  # interval elapsed -> writes
    assert repo.calls == [(2, 1, 10), (2, 3, 10)]


@pytest.mark.asyncio
async def test_final_count_forces_a_write() -> None:
    repo = _FakeRepo()
    rid = uuid.uuid4()
    reporter = ProgressReporter(
        rid,
        repo_factory=lambda session: repo,
        session_scope=_scope_factory(repo),
        min_interval=1000.0,
        clock=lambda: 0.0,
    )
    await reporter.update(3, 1, 5)  # first write
    await reporter.update(3, 5, 5)  # processed == total -> forced even within interval
    assert repo.calls == [(3, 1, 5), (3, 5, 5)]


@pytest.mark.asyncio
async def test_write_errors_are_swallowed() -> None:
    repo = _FakeRepo()
    rid = uuid.uuid4()
    reporter = ProgressReporter(
        rid,
        repo_factory=lambda session: repo,
        session_scope=_scope_factory(repo, raises=True),
        min_interval=0.0,
        clock=lambda: 0.0,
    )
    # Must not raise even though the session scope blows up.
    await reporter.update(2, 1, 10)
    assert repo.calls == []
