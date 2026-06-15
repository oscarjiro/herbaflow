import pytest

from app.security import limiter


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    """Disable per-IP rate limiting in tests (TestClient shares one client key, so the
    suite would otherwise trip the global budget). The rate-limit test re-enables it."""
    previous = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = previous
