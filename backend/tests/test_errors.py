from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import NotFoundProblem, register_error_handlers


def _app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise NotFoundProblem(detail="missing thing")

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("unexpected")

    return app


def test_problem_shape_and_media_type() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["detail"] == "missing thing"


def test_unhandled_is_sanitized_500() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/crash")
    assert resp.status_code == 500
    body = resp.json()
    assert body["status"] == 500
    assert "unexpected" not in body.get("detail", "")
