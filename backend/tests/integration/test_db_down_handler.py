import pytest
from app.routers import analyses
from sqlalchemy.exc import OperationalError

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_db_operational_error_returns_503(client, monkeypatch):
    async def boom(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    # Force the analyses list endpoint's repo call to raise a DB connection error.
    monkeypatch.setattr(analyses.analysis_repo, "list_runs", boom)
    resp = await client.get("/analyses")
    assert resp.status_code == 503
    assert "database" in resp.json()["detail"].lower()
