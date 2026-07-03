"""Unit tests for the non-blocking, best-effort ProgressReporter."""

from __future__ import annotations

import asyncio
import contextlib
import uuid

import pytest

from app.pipeline.progress import ProgressReporter


class _FakeRepo:
    def __init__(self, gate: asyncio.Event | None = None) -> None:
        self.calls: list[tuple[int, int, int]] = []
        self._gate = gate

    async def upsert(self, analysis_id, *, stage, processed, total) -> None:
        if self._gate is not None:
            await self._gate.wait()
        self.calls.append((stage, processed, total))


def _scope_factory(repo, *, raises: bool = False):
    @contextlib.asynccontextmanager
    async def scope():
        if raises:
            raise RuntimeError("db down")
        yield _Session()

    class _Session:
        async def commit(self) -> None:
            pass

    return scope


def _reporter(repo, *, min_interval=1.0, clock=None, raises=False):
    t = {"now": 0.0}
    clk = clock or (lambda: t["now"])
    r = ProgressReporter(
        uuid.uuid4(),
        repo_factory=lambda session: repo,
        session_scope=_scope_factory(repo, raises=raises),
        min_interval=min_interval,
        clock=clk,
    )
    return r, t


@pytest.mark.asyncio
async def test_final_update_is_synchronous_and_durable() -> None:
    repo = _FakeRepo()
    reporter, _ = _reporter(repo, min_interval=1000.0, clock=lambda: 0.0)
    await reporter.update(2, 5, 5)  # processed == total -> written synchronously
    assert repo.calls == [(2, 5, 5)]


@pytest.mark.asyncio
async def test_nonfinal_update_does_not_block_on_the_write() -> None:
    gate = asyncio.Event()  # write cannot complete until we open the gate
    repo = _FakeRepo(gate)
    reporter, _ = _reporter(repo, min_interval=0.0, clock=lambda: 0.0)

    # update returns even though the underlying write is stuck on the gate.
    await asyncio.wait_for(reporter.update(2, 1, 10), timeout=0.5)
    assert repo.calls == []  # write has not landed yet (it is backgrounded)

    gate.set()
    await reporter._drain()
    assert repo.calls == [(2, 1, 10)]


@pytest.mark.asyncio
async def test_bursts_coalesce_to_latest_wins() -> None:
    gate = asyncio.Event()
    repo = _FakeRepo(gate)
    reporter, _ = _reporter(repo, min_interval=0.0, clock=lambda: 0.0)

    # First non-final update launches ONE background write (stuck on the gate).
    await reporter.update(2, 1, 10)
    # More non-final updates arrive while the write is in flight -> only _latest is refreshed.
    await reporter.update(2, 2, 10)
    await reporter.update(2, 7, 10)
    assert repo.calls == []  # nothing landed; still one in-flight write

    gate.set()
    await reporter._drain()
    # The single in-flight write flushed the NEWEST value, not the value it was launched with.
    assert repo.calls == [(2, 7, 10)]


@pytest.mark.asyncio
async def test_final_flushes_latest_after_inflight_drain() -> None:
    gate = asyncio.Event()
    repo = _FakeRepo(gate)
    reporter, _ = _reporter(repo, min_interval=0.0, clock=lambda: 0.0)

    await reporter.update(3, 1, 5)  # backgrounded, stuck on gate
    gate.set()
    await reporter.update(3, 5, 5)  # final: drains the in-flight write, then writes latest
    assert repo.calls[-1] == (3, 5, 5)
    assert (3, 5, 5) in repo.calls


@pytest.mark.asyncio
async def test_throttle_gates_nonfinal_dispatch() -> None:
    repo = _FakeRepo()
    reporter, t = _reporter(repo, min_interval=1.0)
    await reporter.update(2, 1, 10)  # first non-final: dispatches
    await reporter._drain()
    await reporter.update(2, 2, 10)  # within interval -> no dispatch
    await reporter._drain()
    assert repo.calls == [(2, 1, 10)]
    t["now"] = 1.5
    await reporter.update(2, 3, 10)  # interval elapsed -> dispatches
    await reporter._drain()
    assert repo.calls == [(2, 1, 10), (2, 3, 10)]


@pytest.mark.asyncio
async def test_write_errors_are_swallowed() -> None:
    repo = _FakeRepo()
    reporter, _ = _reporter(repo, min_interval=0.0, clock=lambda: 0.0, raises=True)
    # Final path exercises the write synchronously; a blown-up scope must not raise.
    await reporter.update(2, 10, 10)
    assert repo.calls == []
