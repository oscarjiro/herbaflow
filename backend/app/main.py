from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.database import engine
from app.security import limiter, MaxRequestSizeMiddleware
from app.routers import plants, compounds, diseases, analyses

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
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


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
