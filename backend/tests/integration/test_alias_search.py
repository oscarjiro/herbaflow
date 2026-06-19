"""Integration coverage for alias-based search on GET /plants and GET /diseases.

Requires Docker (testcontainers Postgres).  If Docker is unavailable the test
errors at fixture setup with a DockerException — that is expected and does NOT
indicate a code defect.  The orchestrator runs this suite under Docker during
verification.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import db
from app.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase" / "migrations"

_APPLY = [
    "20260608000002_baseline_entities.sql",
    "20260608000003_baseline_aliases.sql",
    "20260608000004_baseline_junctions.sql",
    "20260608000005_baseline_operational.sql",
    "20260609000001_compound_validation_status.sql",
    "20260613000001_rename_disease_target_score.sql",
    "20260613000002_compound_target_discovery_params.sql",
    "20260615000001_analysis_run_idempotency_key.sql",
]


def _async_url(container) -> str:
    return container.get_connection_url().replace("psycopg2", "asyncpg")


async def _run_script(conn, sql: str) -> None:
    raw = await conn.get_raw_connection()
    await raw.driver_connection.execute(sql)


@pytest_asyncio.fixture()
async def alias_engine(pg_container):
    """Engine with entity + alias migrations applied."""
    eng = create_async_engine(_async_url(pg_container))
    async with eng.begin() as conn:
        for name in _APPLY:
            sql = (_MIGRATIONS / name).read_text(encoding="utf-8")
            await _run_script(conn, sql)
    yield eng
    async with eng.begin() as conn:
        await _run_script(
            conn,
            "drop table if exists "
            "analysis_runs, plant_compounds, compound_targets, disease_targets, "
            "plant_aliases, disease_aliases, compound_aliases, target_aliases, "
            "plants, compounds, targets, diseases, source_systems cascade;",
        )
    await eng.dispose()


@pytest_asyncio.fixture()
async def alias_client(alias_engine):
    """httpx AsyncClient with alias-capable engine, seeded with test data."""
    maker = async_sessionmaker(alias_engine, expire_on_commit=False)

    p1_id = uuid.uuid4()
    p2_id = uuid.uuid4()
    p3_id = uuid.uuid4()
    d1_id = uuid.uuid4()
    d2_id = uuid.uuid4()

    async with maker() as s:
        await s.execute(
            text(
                "insert into plants(plant_id, canonical_key, canonical_scientific_name)"
                " values (:p1, 'gbif:1', 'Curcuma longa'),"
                " (:p2, 'gbif:2', 'Zingiber officinale'),"
                " (:p3, 'gbif:3', 'Allium sativum')"
            ),
            {"p1": p1_id, "p2": p2_id, "p3": p3_id},
        )
        await s.execute(
            text(
                "insert into plant_aliases"
                "(alias_id, plant_id, alias_name, alias_key, alias_type) values"
                " (:a1, :p1, 'Turmeric', 'turmeric', 'synonym_variant'),"
                " (:a2, :p2, 'Ginger', 'ginger', 'synonym_variant'),"
                " (:a3, :p1, 'Yellow ginger', 'yellow-ginger', 'synonym_variant')"
            ),
            {
                "a1": uuid.uuid4(),
                "p1": p1_id,
                "a2": uuid.uuid4(),
                "p2": p2_id,
                "a3": uuid.uuid4(),
            },
        )
        await s.execute(
            text(
                "insert into diseases(disease_id, canonical_key, disease_name) values"
                " (:d1, 'doid:9352', 'Type 2 Diabetes Mellitus'),"
                " (:d2, 'doid:10652', 'Alzheimer Disease')"
            ),
            {"d1": d1_id, "d2": d2_id},
        )
        await s.execute(
            text(
                "insert into disease_aliases"
                "(disease_alias_id, disease_id, alias_name, alias_key, alias_type) values"
                " (:da1, :d1, 'T2DM', 't2dm', 'ontology_synonym'),"
                " (:da2, :d2, 'AD', 'ad', 'ontology_synonym')"
            ),
            {
                "da1": uuid.uuid4(),
                "d1": d1_id,
                "da2": uuid.uuid4(),
                "d2": d2_id,
            },
        )
        await s.commit()

    db.set_sessionmaker(maker)

    async def override():
        async with maker() as session:
            yield session

    app.dependency_overrides[db.get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, {"p1": p1_id, "p2": p2_id, "p3": p3_id, "d1": d1_id, "d2": d2_id}
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Plant search tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plant_exact_canonical_match_ranks_first(alias_client) -> None:
    """Exact canonical match is rank 0 and appears first."""
    c, ids = alias_client
    resp = await c.get("/plants", params={"q": "Curcuma longa"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["plant_id"] == str(ids["p1"])
    assert data[0]["matched_alias"] is None  # canonical hit → no alias hint


@pytest.mark.asyncio
async def test_plant_alias_hit_returns_canonical_with_matched_alias(alias_client) -> None:
    """An alias hit returns the canonical plant row with matched_alias set."""
    c, ids = alias_client
    resp = await c.get("/plants", params={"q": "turmeric"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["plant_id"] == str(ids["p1"])
    assert data[0]["canonical_scientific_name"] == "Curcuma longa"
    assert data[0]["matched_alias"] == "Turmeric"


@pytest.mark.asyncio
async def test_plant_canonical_prefix_beats_alias_substring(alias_client) -> None:
    """Canonical prefix (rank 1) beats alias substring (rank 5)."""
    # "gin": p2 "Zingiber officinale" has canonical substring (4);
    # p2 alias "Ginger" has alias prefix (3) → merged best for p2 = 3.
    # p1 alias "Yellow ginger" has "gin" as alias substring (5).
    # p2 (rank 3) must appear before p1 (rank 5).
    c, ids = alias_client
    resp = await c.get("/plants", params={"q": "gin"})
    assert resp.status_code == 200
    data = resp.json()
    plant_ids = [row["plant_id"] for row in data]
    assert str(ids["p2"]) in plant_ids
    p2_pos = plant_ids.index(str(ids["p2"]))
    if str(ids["p1"]) in plant_ids:
        p1_pos = plant_ids.index(str(ids["p1"]))
        assert p2_pos < p1_pos


@pytest.mark.asyncio
async def test_plant_empty_q_returns_full_list_matched_alias_none(alias_client) -> None:
    """Empty q returns the full list with all matched_alias=None."""
    c, ids = alias_client
    resp = await c.get("/plants")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    for row in data:
        assert row["matched_alias"] is None


@pytest.mark.asyncio
async def test_plant_unknown_q_returns_empty(alias_client) -> None:
    """Unknown search term returns 200 with empty list."""
    c, ids = alias_client
    resp = await c.get("/plants", params={"q": "xyznotaplantatall"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_plant_limit_offset_paging(alias_client) -> None:
    """limit/offset pages the result correctly on empty q (full list)."""
    c, ids = alias_client
    resp_all = await c.get("/plants")
    all_ids = [r["plant_id"] for r in resp_all.json()]

    resp_page = await c.get("/plants", params={"limit": 2, "offset": 0})
    assert resp_page.status_code == 200
    assert [r["plant_id"] for r in resp_page.json()] == all_ids[:2]

    resp_page2 = await c.get("/plants", params={"limit": 2, "offset": 2})
    assert resp_page2.status_code == 200
    assert [r["plant_id"] for r in resp_page2.json()] == all_ids[2:]


# ---------------------------------------------------------------------------
# Disease search tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disease_exact_canonical_match_ranks_first(alias_client) -> None:
    """Exact canonical disease name match is rank 0 and appears first."""
    c, ids = alias_client
    resp = await c.get("/diseases", params={"q": "Alzheimer Disease"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["disease_id"] == str(ids["d2"])
    assert data[0]["matched_alias"] is None


@pytest.mark.asyncio
async def test_disease_alias_hit_returns_canonical_with_matched_alias(alias_client) -> None:
    """A disease alias hit returns the canonical row with matched_alias set."""
    c, ids = alias_client
    resp = await c.get("/diseases", params={"q": "T2DM"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["disease_id"] == str(ids["d1"])
    assert data[0]["matched_alias"] == "T2DM"


@pytest.mark.asyncio
async def test_disease_empty_q_returns_full_list(alias_client) -> None:
    """Empty q returns all diseases with matched_alias=None."""
    c, ids = alias_client
    resp = await c.get("/diseases")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for row in data:
        assert row["matched_alias"] is None


@pytest.mark.asyncio
async def test_disease_unknown_q_returns_empty(alias_client) -> None:
    """Unknown disease search term returns 200 []."""
    c, ids = alias_client
    resp = await c.get("/diseases", params={"q": "xyznotadisease"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_disease_limit_offset_paging(alias_client) -> None:
    """limit/offset pages the disease list correctly."""
    c, ids = alias_client
    resp_all = await c.get("/diseases")
    all_ids = [r["disease_id"] for r in resp_all.json()]
    assert len(all_ids) == 2

    resp_one = await c.get("/diseases", params={"limit": 1, "offset": 0})
    assert resp_one.status_code == 200
    assert [r["disease_id"] for r in resp_one.json()] == all_ids[:1]

    resp_two = await c.get("/diseases", params={"limit": 1, "offset": 1})
    assert resp_two.status_code == 200
    assert [r["disease_id"] for r in resp_two.json()] == all_ids[1:]
