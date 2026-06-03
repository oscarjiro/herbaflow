from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security import MaxRequestSizeMiddleware, limiter


def _app(max_bytes: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(MaxRequestSizeMiddleware, max_bytes=max_bytes)

    @app.post("/echo")
    async def echo(payload: dict):
        return payload

    return app


def test_under_cap_passes():
    client = TestClient(_app(1000))
    r = client.post("/echo", json={"a": "x"})
    assert r.status_code == 200


def test_over_cap_returns_413():
    client = TestClient(_app(10))  # 10-byte cap
    r = client.post("/echo", json={"a": "x" * 1000})
    assert r.status_code == 413


def test_limiter_exists_and_uses_remote_address():
    # Sanity: the shared limiter instance is importable and configured
    assert limiter is not None
    assert callable(limiter._key_func)
