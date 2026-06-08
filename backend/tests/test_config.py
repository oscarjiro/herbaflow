from app.config import Settings


def test_async_database_url_swaps_driver() -> None:
    s = Settings(database_url="postgresql://u:p@host:5432/db?sslmode=require")
    assert s.async_database_url.startswith("postgresql+asyncpg://u:p@host:5432/db")


def test_async_database_url_keeps_asyncpg() -> None:
    s = Settings(database_url="postgresql+asyncpg://u:p@host/db")
    assert s.async_database_url == "postgresql+asyncpg://u:p@host/db"
