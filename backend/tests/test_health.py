# backend/tests/test_health.py
import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


def test_health_ok_when_db_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ok() -> None:
        return None

    monkeypatch.setattr(main_module, "check_db", ok)
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_503_when_db_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom() -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(main_module, "check_db", boom)
    resp = TestClient(app, raise_server_exceptions=False).get("/health")
    assert resp.status_code == 503
    assert resp.headers["content-type"] == "application/problem+json"
