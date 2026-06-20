"""AnalysisService.get attaches progress only for a running per-item stage."""

from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace

import pytest

from app.services.analysis import AnalysisService


def _run(status: str):
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        analysis_name=None,
        disease_id=None,
        mode="auto",
        status=status,
        current_stage=3,
        parameters={},
        stage_results={},
        created_at=dt.datetime.now(dt.UTC),
        completed_at=None,
        expires_at=None,
        error_message=None,
    )


class _FakeAnalysisRepo:
    def __init__(self, run):
        self._run = run

    async def get(self, analysis_id):
        return self._run


class _FakeProgressRepo:
    def __init__(self, row):
        self._row = row

    async def get(self, analysis_id):
        return self._row


def _svc(run) -> AnalysisService:
    """Build a minimal AnalysisService with only the analysis_repo wired."""
    return AnalysisService(
        plant_repo=None,
        disease_repo=None,
        analysis_repo=_FakeAnalysisRepo(run),
        compound_repo=None,
    )


@pytest.mark.asyncio
async def test_progress_attached_when_stage3_running(monkeypatch) -> None:
    run = _run("stage_3_running")
    row = SimpleNamespace(stage=3, processed=7, total=10)
    svc = _svc(run)
    monkeypatch.setattr(svc, "progress_repo", _FakeProgressRepo(row), raising=False)
    read = await svc.get(run.analysis_id)
    assert read.progress is not None
    assert (read.progress.stage, read.progress.processed, read.progress.total) == (3, 7, 10)


@pytest.mark.asyncio
async def test_progress_omitted_when_complete(monkeypatch) -> None:
    run = _run("complete")
    row = SimpleNamespace(stage=3, processed=10, total=10)
    svc = _svc(run)
    monkeypatch.setattr(svc, "progress_repo", _FakeProgressRepo(row), raising=False)
    read = await svc.get(run.analysis_id)
    assert read.progress is None
