import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from sqlalchemy.exc import OperationalError, InterfaceError

from app.config import get_settings
from app.database import engine, async_session_factory
from app.repositories import analysis_repo
from app.security import limiter, MaxRequestSizeMiddleware
from app.routers import plants, compounds, diseases, analyses

settings = get_settings()
logger = logging.getLogger(__name__)

REAPER_INTERVAL_SECONDS: float = settings.reaper_interval_seconds
STALE_THRESHOLD_SECONDS: int = settings.stale_run_threshold_seconds


async def _reaper_loop() -> None:
    while True:
        await asyncio.sleep(REAPER_INTERVAL_SECONDS)
        try:
            async with async_session_factory() as session:
                reaped = await analysis_repo.reap_stale_runs(session, STALE_THRESHOLD_SECONDS)
            if reaped:
                logger.info("Reaper marked %d stale run(s) failed", reaped)
        except Exception:
            logger.exception("Reaper sweep failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    reaper = asyncio.create_task(_reaper_loop())
    try:
        yield
    finally:
        reaper.cancel()
        await engine.dispose()


app = FastAPI(
    title="Herbaflow API",
    description="Network pharmacology platform for Indonesian medicinal plants",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Rate limiting (inbound, per-IP) ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# --- Payload-size cap ---
app.add_middleware(MaxRequestSizeMiddleware, max_bytes=settings.max_request_bytes)

# --- CORS lockdown (added LAST so it wraps everything, including 413/429) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


app.include_router(plants.router)
app.include_router(compounds.router)
app.include_router(diseases.router)
app.include_router(analyses.router)


@app.exception_handler(OperationalError)
@app.exception_handler(InterfaceError)
async def _db_unavailable_handler(request, exc):
    logger.warning("Database connection error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is temporarily unavailable. Please try again later."},
    )


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.warning("Health check: database unreachable")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable", "version": "0.1.0"},
        )
    return {"status": "ok", "database": "ok", "version": "0.1.0"}
