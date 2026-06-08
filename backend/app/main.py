"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app import db
from app.config import settings
from app.errors import register_error_handlers
from app.routers import analyses, diseases, plants


def _operation_id(route: APIRoute) -> str:
    """Use the route's function name as the OpenAPI operationId.

    Keeps generated client/SDK names clean (e.g. ``listDiseases``) instead of
    FastAPI's default path-mangled ids (e.g. ``list_diseases_diseases_get``).
    """
    return route.name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.async_database_url:
        db.init_engine()
    try:
        yield
    finally:
        await db.dispose_engine()


app = FastAPI(
    title="Herbaflow API",
    lifespan=lifespan,
    generate_unique_id_function=_operation_id,
)
register_error_handlers(app)
app.include_router(diseases.router)
app.include_router(plants.router)
app.include_router(analyses.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe reporting service status."""
    return {"status": "ok"}
