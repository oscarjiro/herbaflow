from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import async_session_factory
from app.repositories import analysis_repo


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(loop_scope="session")
async def created_runs():
    """Collect analysis_ids created during an integration test and delete them
    on teardown so tests do not leak rows into the live database.

    Usage: append each created analysis_id (as UUID) to the yielded list, e.g.
        created_runs.append(UUID(create_resp.json()["analysis_id"]))
    Deleting the run cascades to its dependent rows. Best-effort: a missing run
    is ignored so a partially-failed test still cleans what it can.
    """
    ids: list[UUID] = []
    yield ids
    async with async_session_factory() as session:
        for analysis_id in ids:
            try:
                await analysis_repo.delete_run(session, analysis_id)
            except Exception:
                pass


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    """Keep the global rate limiter off for normal tests so shared-IP test
    traffic never trips it. The dedicated rate-limit test re-enables it."""
    limiter = getattr(app.state, "limiter", None)
    if limiter is not None:
        prev = limiter.enabled
        limiter.enabled = False
        try:
            limiter.reset()
        except Exception:
            pass
        yield
        limiter.enabled = prev
    else:
        yield
