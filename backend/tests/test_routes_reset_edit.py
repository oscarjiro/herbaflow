"""Unit tests for reset-from and stage-edit HTTP routes (no DB, no network)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import db
from app.errors import ConflictProblem, ValidationProblem
from app.main import app
from app.schemas.analysis import AnalysisRead

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

AID = uuid.uuid4()
STAGE = 2
C1 = uuid.uuid4()
C2 = uuid.uuid4()


def _read(**overrides: Any) -> AnalysisRead:
    defaults = dict(
        analysis_id=AID,
        analysis_name=None,
        disease_id=uuid.uuid4(),
        mode="guided",
        status="stage_2_awaiting_approval",
        current_stage=2,
        parameters={"adme": {}, "stage_edits": {}},
        stage_results={},
        created_at=None,
        completed_at=None,
        expires_at=None,
        error_message=None,
    )
    defaults.update(overrides)
    return AnalysisRead(**defaults)


async def _noop_commit(session: Any) -> None:
    return None


@pytest.fixture(autouse=True)
def _no_db():
    async def fake_session():
        yield None

    app.dependency_overrides[db.get_session] = fake_session
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# reset-from tests
# ---------------------------------------------------------------------------


def test_reset_from_409_when_conflict(monkeypatch) -> None:
    """Returns 409 problem+json when the service raises ConflictProblem."""
    from app.routers import analyses

    class FakeService:
        @classmethod
        def from_session(cls, session: Any):
            return cls()

        async def reset_from(
            self,
            analysis_id: uuid.UUID,
            stage: int,
            param_overrides: dict | None,
            *,
            defer: bool = False,
        ) -> int | None:
            raise ConflictProblem(detail="Run is still running.")

        async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
            return _read()

    monkeypatch.setattr(analyses, "AnalysisService", FakeService)
    monkeypatch.setattr(analyses, "_commit", _noop_commit)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(f"/analyses/{AID}/reset-from/{STAGE}", json={})
    assert resp.status_code == 409
    body = resp.json()
    assert body["status"] == 409
    assert "still running" in body["detail"]


def test_reset_from_422_on_bad_param(monkeypatch) -> None:
    """Returns 422 problem+json when the service raises ValidationProblem (bad param value)."""
    from app.routers import analyses

    class FakeService:
        @classmethod
        def from_session(cls, session: Any):
            return cls()

        async def reset_from(
            self,
            analysis_id: uuid.UUID,
            stage: int,
            param_overrides: dict | None,
            *,
            defer: bool = False,
        ) -> int | None:
            raise ValidationProblem(detail="max_mw must be positive.")

        async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
            return _read()

    monkeypatch.setattr(analyses, "AnalysisService", FakeService)
    monkeypatch.setattr(analyses, "_commit", _noop_commit)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        f"/analyses/{AID}/reset-from/{STAGE}",
        json={"parameters": {str(STAGE): {"max_mw": -1}}},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == 422


def test_reset_from_202_happy_path_passes_stage_overrides(monkeypatch) -> None:
    """
    202 on success (the re-run is scheduled as a BackgroundTask); the route extracts the
    per-stage dict from the body's ``parameters`` and passes it as ``param_overrides``.
    """
    from app.routers import analyses

    captured: dict = {}
    updated = _read(status="complete", current_stage=None)

    class FakeService:
        @classmethod
        def from_session(cls, session: Any):
            return cls()

        async def reset_from(
            self,
            analysis_id: uuid.UUID,
            stage: int,
            param_overrides: dict | None,
            *,
            defer: bool = False,
        ) -> int | None:
            captured["stage"] = stage
            captured["param_overrides"] = param_overrides
            return None

        async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
            return updated

    monkeypatch.setattr(analyses, "AnalysisService", FakeService)
    monkeypatch.setattr(analyses, "_commit", _noop_commit)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        f"/analyses/{AID}/reset-from/{STAGE}",
        json={"parameters": {str(STAGE): {"max_violations": 0}}},
    )
    assert resp.status_code == 202
    # Route must extract the inner dict for the targeted stage.
    assert captured["stage"] == STAGE
    assert captured["param_overrides"] == {"max_violations": 0}
    # Response is the updated AnalysisRead.
    assert resp.json()["status"] == "complete"


def test_reset_from_202_no_parameters_body(monkeypatch) -> None:
    """When body omits ``parameters``, param_overrides is None (plain Redo, no override)."""
    from app.routers import analyses

    captured: dict = {}
    updated = _read(status="complete", current_stage=None)

    class FakeService:
        @classmethod
        def from_session(cls, session: Any):
            return cls()

        async def reset_from(
            self,
            analysis_id: uuid.UUID,
            stage: int,
            param_overrides: dict | None,
            *,
            defer: bool = False,
        ) -> int | None:
            captured["param_overrides"] = param_overrides
            return None

        async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
            return updated

    monkeypatch.setattr(analyses, "AnalysisService", FakeService)
    monkeypatch.setattr(analyses, "_commit", _noop_commit)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(f"/analyses/{AID}/reset-from/{STAGE}", json={})
    assert resp.status_code == 202
    assert captured["param_overrides"] is None


# ---------------------------------------------------------------------------
# stages/{stage}/edit tests
# ---------------------------------------------------------------------------


def test_edit_stage_409_when_not_settled(monkeypatch) -> None:
    """Returns 409 when the service raises ConflictProblem (run still running)."""
    from app.routers import analyses

    class FakeService:
        @classmethod
        def from_session(cls, session: Any):
            return cls()

        async def edit_stage(
            self,
            analysis_id: uuid.UUID,
            stage: int,
            *,
            add: list,
            remove: list,
            defer: bool = False,
        ) -> int | None:
            raise ConflictProblem(detail="Run is still running.")

        async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
            return _read()

    monkeypatch.setattr(analyses, "AnalysisService", FakeService)
    monkeypatch.setattr(analyses, "_commit", _noop_commit)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        f"/analyses/{AID}/stages/1/edit",
        json={"add": [str(C1)], "remove": []},
    )
    assert resp.status_code == 409
    assert resp.json()["status"] == 409


def test_edit_stage_422_on_unknown_add_id(monkeypatch) -> None:
    """Returns 422 when the service raises ValidationProblem (unknown compound id)."""
    from app.routers import analyses

    unknown = uuid.uuid4()

    class FakeService:
        @classmethod
        def from_session(cls, session: Any):
            return cls()

        async def edit_stage(
            self,
            analysis_id: uuid.UUID,
            stage: int,
            *,
            add: list,
            remove: list,
            defer: bool = False,
        ) -> int | None:
            raise ValidationProblem(
                detail="Unknown compound ids.",
                invalid_compound_ids=[str(unknown)],
            )

        async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
            return _read()

    monkeypatch.setattr(analyses, "AnalysisService", FakeService)
    monkeypatch.setattr(analyses, "_commit", _noop_commit)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        f"/analyses/{AID}/stages/1/edit",
        json={"add": [str(unknown)], "remove": []},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == 422
    assert str(unknown) in body["invalid_compound_ids"]


def test_edit_stage_422_on_cap_overflow(monkeypatch) -> None:
    """Returns 422 with cap information when the service raises ValidationProblem (cap overflow)."""
    from app.routers import analyses

    class FakeService:
        @classmethod
        def from_session(cls, session: Any):
            return cls()

        async def edit_stage(
            self,
            analysis_id: uuid.UUID,
            stage: int,
            *,
            add: list,
            remove: list,
            defer: bool = False,
        ) -> int | None:
            raise ValidationProblem(
                detail="Too many compounds for this stage (max 2000, have 1999, adding 5)."
            )

        async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
            return _read()

    monkeypatch.setattr(analyses, "AnalysisService", FakeService)
    monkeypatch.setattr(analyses, "_commit", _noop_commit)

    # Use 5 fake UUIDs (no need to seed 2,000 real compounds; the service enforces the cap).
    fake_adds = [str(uuid.uuid4()) for _ in range(5)]
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        f"/analyses/{AID}/stages/1/edit",
        json={"add": fake_adds, "remove": []},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "max 2000" in body["detail"]


def test_edit_stage_202_happy_path_passes_add_remove(monkeypatch) -> None:
    """202 on success (downstream re-run scheduled); route passes add/remove to the service."""
    from app.routers import analyses

    captured: dict = {}
    updated = _read(status="stage_2_awaiting_approval")

    class FakeService:
        @classmethod
        def from_session(cls, session: Any):
            return cls()

        async def edit_stage(
            self,
            analysis_id: uuid.UUID,
            stage: int,
            *,
            add: list,
            remove: list,
            defer: bool = False,
        ) -> int | None:
            captured["stage"] = stage
            captured["add"] = add
            captured["remove"] = remove

        async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
            return updated

    monkeypatch.setattr(analyses, "AnalysisService", FakeService)
    monkeypatch.setattr(analyses, "_commit", _noop_commit)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        f"/analyses/{AID}/stages/1/edit",
        json={"add": [str(C1)], "remove": [str(C2)]},
    )
    assert resp.status_code == 202
    assert captured["stage"] == 1
    assert C1 in captured["add"]
    assert C2 in captured["remove"]
    assert resp.json()["status"] == "stage_2_awaiting_approval"
