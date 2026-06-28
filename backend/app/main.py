"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import db
from app.config import settings
from app.db import check_db
from app.errors import ServiceUnavailableError, register_error_handlers
from app.logging_config import configure_logging
from app.repositories.analysis import AnalysisRepository
from app.routers import analyses, compounds, diseases, export, plants, targets
from app.security import (
    PayloadSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    limiter,
    rate_limit_handler,
)

logger = logging.getLogger("herbaflow.app")

_REAPER_MESSAGE = "The server restarted while this analysis was running. Please run it again."


async def _run_startup_reaper() -> None:
    """Fail any runs that were in-flight when the server process last died.

    Safe on startup because a fresh process has no in-flight background tasks.
    Any run still in a running or pending state at startup was stranded by a crash
    or forceful restart and can never resume.  A failure here is logged as a warning
    and does not block startup.
    """
    try:
        async with db.session_scope() as session:
            n = await AnalysisRepository(session).fail_stranded(message=_REAPER_MESSAGE)
            await session.commit()
        logger.info("startup reaper: failed %d stranded run(s)", n)
    except Exception:
        logger.warning(
            "startup reaper could not mark stranded runs failed; they remain in their"
            " current status and must be resolved manually",
            exc_info=True,
        )


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
        await _run_startup_reaper()
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
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[arg-type]
# Middleware is applied in reverse order of registration (last added = outermost).
# Register CORS LAST so every response — including short-circuited 413/429 — carries
# CORS headers (the browser hides bodies on responses missing them).
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(PayloadSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
app.add_middleware(SecurityHeadersMiddleware)
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
