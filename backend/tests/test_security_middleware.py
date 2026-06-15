from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_oversized_body_rejected_413():
    big = "x" * (settings.max_request_bytes + 1)
    resp = client.post("/analyses", content=big, headers={"Content-Type": "application/json"})
    assert resp.status_code == 413
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["status"] == 413


def test_small_body_not_rejected_by_cap():
    # A small (invalid) body must pass the cap and reach validation, never 413.
    resp = client.post("/analyses", json={"plant_ids": ["not-a-uuid"]})
    assert resp.status_code != 413
