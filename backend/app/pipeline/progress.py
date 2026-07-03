"""Non-blocking, best-effort per-run progress writer.

Writes the analysis_run_progress side table on its OWN session so it never
contends with the run row's lock, and never raises into a running stage.

The hot stage loop calls update() once per item. Non-final updates dispatch a
single coalesced background write (latest-wins, at most one in flight) so the
loop never blocks on the remote commit. The final update (processed >= total)
is written synchronously so the terminal value is durable and the bar reaches
100%.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

from app import db
from app.repositories.analysis_progress import AnalysisProgressRepository

logger = logging.getLogger("herbaflow.pipeline")


class ProgressReporter:
    def __init__(
        self,
        analysis_id: uuid.UUID,
        *,
        session_scope: Callable[[], Any] = db.session_scope,
        repo_factory: Callable[[Any], Any] = AnalysisProgressRepository,
        min_interval: float = 0.4,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._analysis_id = analysis_id
        self._session_scope = session_scope
        self._repo_factory = repo_factory
        self._min_interval = min_interval
        self._clock = clock
        self._last = float("-inf")
        self._latest: tuple[int, int, int] | None = None
        self._inflight: asyncio.Task[None] | None = None

    async def update(self, stage: int, processed: int, total: int) -> None:
        # Record newest state first: background AND final writes flush THIS value, so a
        # late background write can never clobber a newer value with a stale one.
        self._latest = (stage, processed, total)
        if processed >= total:
            # Terminal value: make it durable. Wait out any in-flight write, then write.
            await self._drain()
            self._last = self._clock()
            await self._write_once()
            return
        if self._inflight is not None:
            return  # a write is running; it flushes the newest _latest when it lands
        now = self._clock()
        if (now - self._last) < self._min_interval:
            return
        self._last = now
        self._inflight = asyncio.create_task(self._write_loop())

    async def _write_loop(self) -> None:
        try:
            await self._write_once()
        finally:
            self._inflight = None

    async def _drain(self) -> None:
        task = self._inflight
        if task is not None:
            with contextlib.suppress(Exception):
                await task

    async def _write_once(self) -> None:
        latest = self._latest
        if latest is None:
            return
        stage, processed, total = latest
        try:
            async with self._session_scope() as session:
                repo = self._repo_factory(session)
                await repo.upsert(self._analysis_id, stage=stage, processed=processed, total=total)
                await session.commit()
        except Exception as exc:  # noqa: BLE001 — progress is best-effort, never fail a run
            logger.debug("progress write skipped for %s: %s", str(self._analysis_id)[:8], exc)
