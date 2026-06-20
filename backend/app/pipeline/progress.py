"""Throttled, best-effort per-run progress writer.

Writes the analysis_run_progress side table on its OWN session so it never
contends with the run row's lock, and never raises into a running stage.
"""

from __future__ import annotations

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

    async def update(self, stage: int, processed: int, total: int) -> None:
        now = self._clock()
        is_final = processed >= total
        if not is_final and (now - self._last) < self._min_interval:
            return
        self._last = now
        try:
            async with self._session_scope() as session:
                repo = self._repo_factory(session)
                await repo.upsert(self._analysis_id, stage=stage, processed=processed, total=total)
                await session.commit()
        except Exception as exc:  # noqa: BLE001 — progress is best-effort, never fail a run
            logger.debug("progress write skipped for %s: %s", str(self._analysis_id)[:8], exc)
