"""Unit tests for the deferred background entrypoint ``run_stages_task``.

The background task owns its session and MUST mark the run ``failed`` if any stage
runner raises — otherwise a crash (e.g. a provider outage) leaves the run stuck in a
``*_running`` status forever. This guard covers the create path AND the four mutating
endpoints (advance / reset-from / edit), which all schedule this task.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.pipeline import engine
from app.pipeline.stages import stage5


class _FakeRepo:
    def __init__(self, run: SimpleNamespace) -> None:
        self.run = run

    async def get(self, analysis_id: uuid.UUID) -> SimpleNamespace:
        return self.run

    async def set_status(
        self, run: SimpleNamespace, status: str, *, current_stage: int | None = None
    ) -> None:
        run.status = status
        if current_stage is not None:
            run.current_stage = current_stage

    async def set_stage_result(self, run: SimpleNamespace, stage: int, result: dict) -> None:
        run.stage_results[str(stage)] = result

    async def complete(self, run: SimpleNamespace) -> None:
        run.status = "complete"

    async def fail(self, run: SimpleNamespace, message: str) -> None:
        run.status = "failed"
        run.error_message = message


def _run() -> SimpleNamespace:
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        mode="auto",
        status="stage_1_running",
        current_stage=1,
        stage_results={},
        error_message=None,
        parameters={},
    )


@pytest.mark.asyncio
async def test_run_stages_task_marks_failed_when_runner_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run()
    committed: list[bool] = []

    async def _commit() -> None:
        committed.append(True)

    fake_session = SimpleNamespace(commit=_commit)

    @asynccontextmanager
    async def fake_scope():
        yield fake_session

    async def boom(_run: SimpleNamespace) -> dict:
        raise RuntimeError("provider outage")

    monkeypatch.setattr(engine.db, "session_scope", fake_scope)
    monkeypatch.setattr(engine, "AnalysisRepository", lambda session: _FakeRepo(run))
    monkeypatch.setattr(engine, "build_runners", lambda session: {1: boom, 2: boom, 3: boom})

    await engine.run_stages_task(run.analysis_id, 1)

    assert run.status == "failed"
    assert "provider outage" in (run.error_message or "")
    assert committed == [True], "the failed mark must be committed"


@pytest.mark.asyncio
async def test_run_stages_task_completes_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run()

    async def _commit() -> None:
        return None

    fake_session = SimpleNamespace(commit=_commit)

    @asynccontextmanager
    async def fake_scope():
        yield fake_session

    async def stage1(_run: SimpleNamespace) -> dict:
        return {"count": 1, "compounds": [{"compound_id": "c0", "canonical_name": "C0"}]}

    async def stage2(_run: SimpleNamespace) -> dict:
        return {"count": 1, "passed": [], "filtered": [], "annotations": {}, "state": "computed"}

    async def stage3(_run: SimpleNamespace) -> dict:
        return {
            "targets": [{"target_id": "t0", "canonical_name": "T0"}],
            "compound_targets": [],
            "per_compound": {},
            "coverage_pct": 0.0,
            "count": 1,
            "state": "computed",
        }

    async def stage4(_run: SimpleNamespace) -> dict:
        return {
            "targets": [{"target_id": "t0", "canonical_name": "T0"}],
            "disease_targets": [{"target_id": "t0", "score": 0.5}],
            "count": 1,
            "min_score_applied": 0.3,
            "state": "computed",
        }

    async def stage5_runner(r: SimpleNamespace) -> dict:
        # S3/S4 both carry t0 -> overlap count 1 -> S5 succeeds and the run completes.
        return await stage5.run(None, r)

    monkeypatch.setattr(engine.db, "session_scope", fake_scope)
    monkeypatch.setattr(engine, "AnalysisRepository", lambda session: _FakeRepo(run))
    monkeypatch.setattr(
        engine,
        "build_runners",
        lambda session: {1: stage1, 2: stage2, 3: stage3, 4: stage4, 5: stage5_runner},
    )

    await engine.run_stages_task(run.analysis_id, 1)

    assert run.status == "complete"
