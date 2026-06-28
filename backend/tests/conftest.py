import logging

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


@pytest.fixture(autouse=True)
def _herbaflow_log_propagate():
    """Re-enable propagation on the herbaflow logger during tests.

    configure_logging() sets propagate=False to avoid double-emission through uvicorn's root
    handler in production. In tests there is no uvicorn root handler, so disabling propagation
    prevents caplog from capturing herbaflow.* records. This fixture temporarily restores
    propagation so caplog works correctly with herbaflow.* loggers.
    """
    herbaflow_logger = logging.getLogger("herbaflow")
    previous = herbaflow_logger.propagate
    herbaflow_logger.propagate = True
    yield
    herbaflow_logger.propagate = previous
