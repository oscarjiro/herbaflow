"""Async SQLAlchemy engine, session factory, and the request session dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _prepare(url: str) -> tuple[str, dict[str, Any]]:
    """Strip libpq-only query params asyncpg rejects; map sslmode -> ssl connect arg."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    connect_args: dict[str, Any] = {}
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = True
    clean = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return clean, connect_args


def init_engine(database_url: str | None = None) -> AsyncEngine:
    """Create the engine + session factory. Call once on app startup (lifespan)."""
    global _engine, _sessionmaker
    url, connect_args = _prepare(database_url or settings.async_database_url)
    _engine = create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        connect_args={**connect_args, "timeout": settings.db_connect_timeout},
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def dispose_engine() -> None:
    """Dispose the engine on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def set_sessionmaker(maker: async_sessionmaker[AsyncSession]) -> None:
    """Test hook: bind a session factory without a global engine."""
    global _sessionmaker
    _sessionmaker = maker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped AsyncSession."""
    if _sessionmaker is None:
        raise RuntimeError("engine not initialized; call init_engine() in the app lifespan")
    async with _sessionmaker() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Standalone session for background work (outside a request)."""
    if _sessionmaker is None:
        raise RuntimeError("engine not initialized; call init_engine() in the app lifespan")
    async with _sessionmaker() as session:
        yield session
