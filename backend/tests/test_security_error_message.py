"""Regression guard: unhandled exceptions never leak internal details to the client."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_unhandled_error_never_leaks_traceback() -> None:
    # Force an unhandled error via a route that raises, and assert the body is the
    # sanitized 500 problem+json with no traceback/exception text.
    client = TestClient(app, raise_server_exceptions=False)

    @app.get("/_boom")
    async def _boom() -> None:  # pragma: no cover - test-only route
        raise RuntimeError("secret internal detail")

    resp = client.get("/_boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["title"] == "Internal Server Error"
    assert "secret internal detail" not in resp.text
    assert "Traceback" not in resp.text
