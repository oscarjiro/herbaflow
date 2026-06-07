"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="Herbaflow API")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe reporting service status."""
    return {"status": "ok"}
