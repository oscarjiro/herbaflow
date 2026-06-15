from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from app.security import limiter, rate_limit_handler


def test_rate_limit_returns_429_problem_json():
    mini = FastAPI()
    mini.state.limiter = limiter
    mini.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    @mini.get("/ping")
    @limiter.limit("2/minute")
    async def ping(request: Request) -> dict[str, bool]:
        return {"ok": True}

    limiter.enabled = True
    try:
        client = TestClient(mini, raise_server_exceptions=False)
        assert client.get("/ping").status_code == 200
        assert client.get("/ping").status_code == 200
        resp = client.get("/ping")
        assert resp.status_code == 429
        assert resp.headers["content-type"].startswith("application/problem+json")
        assert resp.json()["status"] == 429
        assert "Retry-After" in resp.headers
    finally:
        limiter.enabled = False
