"""CORS middleware lets the Vite dev origin call the API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_cors_allows_dev_origin() -> None:
    client = TestClient(app)
    resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_preflight_is_handled() -> None:
    client = TestClient(app)
    resp = client.options(
        "/compounds/validate",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
