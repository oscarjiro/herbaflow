import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


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
