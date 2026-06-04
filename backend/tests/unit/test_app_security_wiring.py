from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_allowed_origin_is_reflected():
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_disallowed_origin_not_reflected():
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"


def test_credentials_not_allowed():
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    # allow_credentials=False -> header absent or not "true"
    assert r.headers.get("access-control-allow-credentials") != "true"


def test_oversize_payload_rejected_with_413():
    big = {"data": "x" * 3_000_000}  # ~3 MB > 2 MB cap
    r = client.post("/analyses", json=big)
    assert r.status_code == 413


def test_limiter_registered():
    assert getattr(app.state, "limiter", None) is not None
