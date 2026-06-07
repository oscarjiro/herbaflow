"""FastAPI application entry point. Phase 0: liveness probe only."""

from fastapi import FastAPI

app = FastAPI(title="Herbaflow API")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. DB-awareness is added in a later phase."""
    return {"status": "ok"}
