"""Unit test: _run_startup_reaper wires fail_stranded into the startup path.

Tests that calling _run_startup_reaper() causes AnalysisRepository.fail_stranded
to be invoked with the correct message. Uses monkeypatching to avoid needing a
real database.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

import app.main as main_module
from app import db

REAPER_MESSAGE = "The server restarted while this analysis was running. Please run it again."


async def test_startup_reaper_calls_fail_stranded(monkeypatch: pytest.MonkeyPatch) -> None:
    """_run_startup_reaper calls AnalysisRepository.fail_stranded with the reaper message."""
    fail_stranded_calls: list[str] = []

    class FakeSession:
        async def commit(self) -> None:
            pass

    class FakeRepo:
        def __init__(self, session: object) -> None:
            pass

        async def fail_stranded(self, *, message: str) -> int:
            fail_stranded_calls.append(message)
            return 3

    @asynccontextmanager
    async def fake_scope():  # type: ignore[override]
        yield FakeSession()

    monkeypatch.setattr(db, "session_scope", fake_scope)
    monkeypatch.setattr(main_module, "AnalysisRepository", FakeRepo)

    await main_module._run_startup_reaper()

    assert len(fail_stranded_calls) == 1, "fail_stranded must be called exactly once on startup"
    assert fail_stranded_calls[0] == REAPER_MESSAGE


async def test_startup_reaper_swallows_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reaper failure must not propagate — startup continues."""

    @asynccontextmanager
    async def boom():  # type: ignore[override]
        raise RuntimeError("db exploded")
        yield  # unreachable but required by asynccontextmanager

    monkeypatch.setattr(db, "session_scope", boom)

    # Must not raise
    await main_module._run_startup_reaper()
