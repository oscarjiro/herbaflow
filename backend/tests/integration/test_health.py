import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_health_reports_db_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
