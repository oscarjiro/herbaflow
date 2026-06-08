import pytest

from app import db


@pytest.mark.asyncio
async def test_get_session_without_init_raises() -> None:
    db._sessionmaker = None  # ensure uninitialized
    with pytest.raises(RuntimeError):
        async for _ in db.get_session():
            pass


def test_prepare_strips_sslmode() -> None:
    url, connect_args = db._prepare("postgresql+asyncpg://u:p@h:5432/db?sslmode=require")
    assert "sslmode" not in url
    assert connect_args == {"ssl": True}


def test_prepare_local_has_no_ssl() -> None:
    url, connect_args = db._prepare("postgresql+asyncpg://u:p@localhost:5432/db")
    assert connect_args == {}
