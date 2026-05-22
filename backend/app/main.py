from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine
from app.models import ImportBatch  # noqa: F401 — ensures import_batches table registered before FK resolution
from app.routers import plants, compounds, diseases, analyses


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(plants.router)
app.include_router(compounds.router)
app.include_router(diseases.router)
app.include_router(analyses.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
