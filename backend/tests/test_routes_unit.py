"""Unit tests for HTTP routers (no DB, no network)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture(autouse=True)
def _no_db():
    async def fake_session():
        yield None

    app.dependency_overrides[db.get_session] = fake_session
    yield
    app.dependency_overrides.clear()


def test_create_returns_202_and_schedules(monkeypatch) -> None:
    from app.routers import analyses
    from app.schemas.analysis import AnalysisRead

    created = AnalysisRead(
        analysis_id=uuid.uuid4(),
        analysis_name=None,
        disease_id=uuid.uuid4(),
        mode="auto",
        status="pending",
        current_stage=None,
        stage_results={},
        created_at=None,
        completed_at=None,
        expires_at=None,
        error_message=None,
    )

    class FakeService:
        @classmethod
        def from_session(cls, session):
            return cls()

        async def create(self, payload):
            return created

    scheduled: list = []
    monkeypatch.setattr(analyses, "AnalysisService", FakeService)
    monkeypatch.setattr(analyses, "run_analysis_task", lambda aid: scheduled.append(aid))
    monkeypatch.setattr(analyses, "_commit", _noop_commit)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/analyses",
        json={"plant_ids": [str(uuid.uuid4())], "disease_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "pending"
    assert len(scheduled) == 1


async def _noop_commit(session) -> None:
    return None
