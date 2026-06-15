# backend/tests/test_db_config.py
from app import db
from app.config import settings


def test_init_engine_applies_pool_settings() -> None:
    engine = db.init_engine("postgresql+asyncpg://u:p@localhost:5432/x")
    try:
        pool = engine.sync_engine.pool
        assert pool.size() == settings.db_pool_size  # type: ignore[attr-defined]
        # pool_timeout is the checkout wait ceiling (fail fast on a dead DB).
        assert pool._timeout == settings.db_pool_timeout  # type: ignore[attr-defined]
    finally:
        # init_engine sets module globals; reset so other tests re-init cleanly.
        db._engine = None
        db._sessionmaker = None
