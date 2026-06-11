from pathlib import Path

from app.config import Settings


def test_env_file_is_repo_root_absolute() -> None:
    """env_file must be an absolute repo-root path so it loads regardless of cwd."""
    env_file = Settings.model_config["env_file"]
    assert isinstance(env_file, Path)
    assert env_file.is_absolute()
    assert env_file == Path(__file__).resolve().parents[2] / ".env"


def test_async_database_url_swaps_driver() -> None:
    s = Settings(database_url="postgresql://u:p@host:5432/db?sslmode=require")
    assert s.async_database_url.startswith("postgresql+asyncpg://u:p@host:5432/db")


def test_async_database_url_keeps_asyncpg() -> None:
    s = Settings(database_url="postgresql+asyncpg://u:p@host/db")
    assert s.async_database_url == "postgresql+asyncpg://u:p@host/db"
