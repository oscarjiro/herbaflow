# backend/tests/scientific/conftest.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app import db
from app.main import app

_MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
_APPLY = [
    "20260608000002_baseline_entities.sql",
    "20260608000004_baseline_junctions.sql",
    "20260608000005_baseline_operational.sql",
    "20260609000001_compound_validation_status.sql",
    "20260613000001_rename_disease_target_score.sql",
    "20260613000002_compound_target_discovery_params.sql",
    "20260615000001_analysis_run_idempotency_key.sql",
    "20260620000001_analysis_run_progress.sql",
    "20260702000001_wave3_schema_trim.sql",
]
FIXTURES = Path(__file__).parent / "fixtures"


def _async_url(container: PostgresContainer) -> str:
    return container.get_connection_url().replace("psycopg2", "asyncpg")


async def _run_script(conn, sql: str) -> None:
    raw = await conn.get_raw_connection()
    await raw.driver_connection.execute(sql)


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest_asyncio.fixture()
async def engine(pg_container):
    eng = create_async_engine(_async_url(pg_container))
    async with eng.begin() as conn:
        for name in _APPLY:
            await _run_script(conn, (_MIGRATIONS / name).read_text(encoding="utf-8"))
    yield eng
    async with eng.begin() as conn:
        await _run_script(
            conn,
            "drop table if exists analysis_run_progress, analysis_runs, plant_compounds, "
            "compound_targets, disease_targets, plants, compounds, targets, diseases cascade;",
        )
    await eng.dispose()


@pytest_asyncio.fixture()
async def golden_client(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    db.set_sessionmaker(maker)

    async def override():
        async with maker() as s:
            yield s

    app.dependency_overrides[db.get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, engine
    app.dependency_overrides.clear()


@pytest.fixture()
def fixtures_dir() -> Path:
    return FIXTURES


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def poll_run(
    client: httpx.AsyncClient, run_id: str, *, max_iters: int = 180
) -> dict[str, Any]:
    """Poll ``GET /analyses/{run_id}`` until the run settles (complete/failed) or iters run out.

    The single home for the golden suite's poll-until-settled loop, reused by the scientific tests
    (``max_iters=180``) and both report drivers (``max_iters=300``).
    """
    state: dict[str, Any] = {}
    for _ in range(max_iters):
        state = (await client.get(f"/analyses/{run_id}")).json()
        if state.get("status") in {"complete", "failed"}:
            break
    return state
