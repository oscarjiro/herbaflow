"""Real-Postgres integration fixtures via testcontainers.

Applies only the entity, junction, and operational baseline migrations (not cron/RLS,
which need extensions/roles a vanilla image lacks and which the slice does not exercise).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
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
]


def _async_url(container: PostgresContainer) -> str:
    # testcontainers default url is psycopg2; swap the driver for asyncpg.
    return container.get_connection_url().replace("psycopg2", "asyncpg")


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


async def _run_script(conn, sql: str) -> None:
    # Migration files hold multiple statements; asyncpg's prepared-statement path
    # (used by exec_driver_sql) rejects that, so run them through the raw asyncpg
    # connection's simple-query execute, which accepts multi-statement scripts.
    raw = await conn.get_raw_connection()
    await raw.driver_connection.execute(sql)


@pytest_asyncio.fixture()
async def engine(pg_container):
    eng = create_async_engine(_async_url(pg_container))
    async with eng.begin() as conn:
        for name in _APPLY:
            sql = (_MIGRATIONS / name).read_text(encoding="utf-8")
            await _run_script(conn, sql)
    yield eng
    async with eng.begin() as conn:
        await _run_script(
            conn,
            "drop table if exists analysis_runs, plant_compounds, compound_targets, "
            "disease_targets, plants, compounds, targets, diseases, source_systems cascade;",
        )
    await eng.dispose()


@pytest_asyncio.fixture()
async def session(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s


@pytest_asyncio.fixture()
async def seeded(engine):
    """Seed two plants (one with compounds, one empty), compounds, links, a disease."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    ids = {
        "plant_full": uuid.uuid4(),
        "plant_empty": uuid.uuid4(),
        "c1": uuid.uuid4(),
        "c2": uuid.uuid4(),
        "disease": uuid.uuid4(),
    }
    async with maker() as session:
        await session.execute(
            text(
                "insert into plants(plant_id, canonical_key, canonical_scientific_name) "
                "values (:p1,'gbif:1','Aaa bbb'),(:p2,'gbif:2','Ccc ddd')"
            ),
            {"p1": ids["plant_full"], "p2": ids["plant_empty"]},
        )
        await session.execute(
            text(
                "insert into compounds("
                "  compound_id, canonical_key, canonical_name,"
                "  molecular_weight, logp, hbond_donors, hbond_acceptors,"
                "  tpsa, rotatable_bonds, num_ro5_violations,"
                "  validation_status"
                ") values ("
                "  :c1,'inchikey:A','Alpha',"
                "  46.07,-0.14,1,1,20.23,0,0,'externally_validated'"
                "),("
                "  :c2,'inchikey:B','Beta',"
                "  46.07,-0.14,1,1,20.23,0,0,'externally_validated'"
                ")"
            ),
            {"c1": ids["c1"], "c2": ids["c2"]},
        )
        await session.execute(
            text(
                "insert into plant_compounds(plant_compound_id, plant_id, compound_id) "
                "values (:i1,:p,:c1),(:i2,:p,:c2)"
            ),
            {
                "i1": uuid.uuid4(),
                "i2": uuid.uuid4(),
                "p": ids["plant_full"],
                "c1": ids["c1"],
                "c2": ids["c2"],
            },
        )
        await session.execute(
            text(
                "insert into diseases(disease_id, canonical_key, disease_name) "
                "values (:d,'doid:1','Test Disease')"
            ),
            {"d": ids["disease"]},
        )
        await session.commit()
    return ids


@pytest_asyncio.fixture()
async def seed_compound(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    cid = uuid.uuid4()
    async with maker() as s:
        await s.execute(
            text(
                "insert into compounds"
                "(compound_id, canonical_key, canonical_name, validation_status) "
                "values (:c, 'inchikey:CT0', 'CTComp', 'externally_validated')"
            ),
            {"c": cid},
        )
        await s.commit()
    return cid


@pytest_asyncio.fixture()
async def seed_target(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    tid = uuid.uuid4()
    async with maker() as s:
        await s.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol) "
                "values (:t, 'uniprot:PCT0', 'CTGENE')"
            ),
            {"t": tid},
        )
        await s.commit()
    return tid


@pytest_asyncio.fixture()
async def client(engine, seeded):
    """httpx AsyncClient against the app, with get_session bound to the test engine."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    db.set_sessionmaker(maker)

    async def override():
        async with maker() as session:
            yield session

    app.dependency_overrides[db.get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, seeded
    app.dependency_overrides.clear()
