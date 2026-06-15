"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app import db
from app.config import settings
from app.db import check_db
from app.errors import ServiceUnavailableError, register_error_handlers
from app.logging_config import configure_logging
from app.routers import analyses, compounds, diseases, export, plants, targets

logger = logging.getLogger("herbaflow.app")


def _operation_id(route: APIRoute) -> str:
    """Use the route's function name as the OpenAPI operationId.

    Keeps generated client/SDK names clean (e.g. ``listDiseases``) instead of
    FastAPI's default path-mangled ids (e.g. ``list_diseases_diseases_get``).
    """
    return route.name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    if settings.async_database_url:
        db.init_engine()
        logger.info("database engine initialized")
    else:
        logger.warning("DATABASE_URL not set — database routes will fail until it is configured")
    try:
        yield
    finally:
        await db.dispose_engine()


app = FastAPI(
    title="Herbaflow API",
    lifespan=lifespan,
    generate_unique_id_function=_operation_id,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.include_router(diseases.router)
app.include_router(plants.router)
app.include_router(analyses.router)
app.include_router(compounds.router)
app.include_router(targets.router)
app.include_router(export.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Readiness probe: 200 when the database is reachable, 503 otherwise."""
    try:
        await check_db()
    except Exception as exc:  # noqa: BLE001 — any DB failure means not-ready
        raise ServiceUnavailableError(detail="The database is unavailable.") from exc
    return {"status": "ok"}
