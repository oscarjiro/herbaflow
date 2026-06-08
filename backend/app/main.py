"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.config import settings
from app.errors import register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.async_database_url:
        db.init_engine()
    try:
        yield
    finally:
        await db.dispose_engine()


app = FastAPI(title="Herbaflow API", lifespan=lifespan)
register_error_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe reporting service status."""
    return {"status": "ok"}
