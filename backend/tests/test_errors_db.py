# backend/tests/test_errors_db.py
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.errors import register_error_handlers


def _app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise OperationalError("SELECT 1", None, Exception("connection refused"))

    @app.get("/refused")
    def refused() -> dict[str, str]:
        # A dead database connect surfaces as a raw OSError (asyncpg does not get wrapped
        # by SQLAlchemy at connect time); it must still map to 503, not 500.
        raise ConnectionRefusedError("[WinError 1225] connection refused")

    return app


def test_db_error_returns_503_problem_json() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 503
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["status"] == 503
    assert body["title"] == "Service Unavailable"


def test_raw_connection_error_returns_503_problem_json() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/refused")
    assert resp.status_code == 503
    assert resp.headers["content-type"] == "application/problem+json"
    assert resp.json()["title"] == "Service Unavailable"
