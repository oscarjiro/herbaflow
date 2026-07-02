"""Integration coverage for canonical-name search on GET /plants and GET /diseases.

Synonym/alias search was retired with the alias tables (Wave 3 schema trim); search now
matches only the canonical scientific name / disease name (``matched_alias`` is always
``None``). Tests whose entire purpose was an alias-synonym DB hit were removed — see the
one-line notes below.

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
    "20260608000004_baseline_junctions.sql",
    "20260608000005_baseline_operational.sql",
    "20260609000001_compound_validation_status.sql",
    "20260613000001_rename_disease_target_score.sql",
    "20260613000002_compound_target_discovery_params.sql",
    "20260615000001_analysis_run_idempotency_key.sql",
    "20260620000001_analysis_run_progress.sql",
    "20260702000001_wave3_schema_trim.sql",
]


def _async_url(container) -> str:
    return container.get_connection_url().replace("psycopg2", "asyncpg")


async def _run_script(conn, sql: str) -> None:
    raw = await conn.get_raw_connection()
    await raw.driver_connection.execute(sql)


@pytest_asyncio.fixture()
async def alias_engine(pg_container):
    """Engine with the full baseline + schema-trim migrations applied."""
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
            "analysis_run_progress, analysis_runs, plant_compounds, compound_targets, "
            "disease_targets, plants, compounds, targets, diseases cascade;",
        )
    await eng.dispose()


@pytest_asyncio.fixture()
async def alias_client(alias_engine):
    """httpx AsyncClient with the trimmed-schema engine, seeded with test data."""
    maker = async_sessionmaker(alias_engine, expire_on_commit=False)

    p1_id = uuid.uuid4()
    p2_id = uuid.uuid4()
    p3_id = uuid.uuid4()
    d1_id = uuid.uuid4()
    d2_id = uuid.uuid4()

    async with maker() as s:
        await s.execute(
            text(
                "insert into plants(plant_id, gbif_key, canonical_scientific_name)"
                " values (:p1, '1', 'Curcuma longa'),"
                " (:p2, '2', 'Zingiber officinale'),"
                " (:p3, '3', 'Allium sativum')"
            ),
            {"p1": p1_id, "p2": p2_id, "p3": p3_id},
        )
        await s.execute(
            text(
                "insert into diseases(disease_id, ontology_id, disease_name) values"
                " (:d1, 'doid:9352', 'Type 2 Diabetes Mellitus'),"
                " (:d2, 'doid:10652', 'Alzheimer Disease')"
            ),
            {"d1": d1_id, "d2": d2_id},
        )
        c1, c2, c3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        t1, t2 = uuid.uuid4(), uuid.uuid4()
        await s.execute(
            text(
                "insert into compounds(compound_id, inchi_key, canonical_name) values"
                " (:c1, 'AAAAAAAAAAAAAA-AAAAAAAAAA-A', 'Curcumin'),"
                " (:c2, 'BBBBBBBBBBBBBB-BBBBBBBBBB-B', 'Demethoxycurcumin'),"
                " (:c3, 'CCCCCCCCCCCCCC-CCCCCCCCCC-C', 'Gingerol')"
            ),
            {"c1": c1, "c2": c2, "c3": c3},
        )
        await s.execute(
            text(
                "insert into plant_compounds(plant_compound_id, plant_id, compound_id) values"
                " (:r1, :p1, :c1), (:r2, :p1, :c2), (:r3, :p2, :c3)"
            ),
            {
                "r1": uuid.uuid4(),
                "p1": p1_id,
                "c1": c1,
                "r2": uuid.uuid4(),
                "c2": c2,
                "r3": uuid.uuid4(),
                "p2": p2_id,
                "c3": c3,
            },
        )
        await s.execute(
            text(
                "insert into targets(target_id, uniprot_accession, gene_symbol) values"
                " (:t1, 'P00001', 'TNF'), (:t2, 'P00002', 'IL6')"
            ),
            {"t1": t1, "t2": t2},
        )
        await s.execute(
            text(
                "insert into disease_targets"
                "(disease_target_id, disease_id, target_id, opentargets_score) values"
                " (:x1, :d1, :t1, 0.9), (:x2, :d1, :t2, 0.4)"
            ),
            {"x1": uuid.uuid4(), "d1": d1_id, "t1": t1, "x2": uuid.uuid4(), "t2": t2},
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
    assert data[0]["matched_alias"] is None  # canonical hit -> no alias hint


# NOTE: test_plant_alias_hit_returns_canonical_with_matched_alias removed — its entire
# purpose was an alias-synonym DB hit ("turmeric" -> Curcuma longa), which no longer exists
# now that alias tables are retired (search is canonical-name-only).


# NOTE: test_plant_alias_prefix_beats_alias_substring removed — its entire purpose was
# comparing rank ordering between two ALIAS rows, which no longer exist.


@pytest.mark.asyncio
async def test_plant_canonical_substring_matches(alias_client) -> None:
    """A substring of the canonical name still matches (name-only search)."""
    c, ids = alias_client
    resp = await c.get("/plants", params={"q": "officinale"})
    assert resp.status_code == 200
    data = resp.json()
    plant_ids = [row["plant_id"] for row in data]
    assert str(ids["p2"]) in plant_ids
    for row in data:
        assert row["matched_alias"] is None


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


# NOTE: test_disease_alias_hit_returns_canonical_with_matched_alias removed — its entire
# purpose was an alias-synonym DB hit ("T2DM" -> Type 2 Diabetes Mellitus), which no longer
# exists now that alias tables are retired (search is canonical-name-only).


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


# ---------------------------------------------------------------------------
# Catalog count tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plant_search_includes_compound_count(alias_client) -> None:
    c, ids = alias_client
    resp = await c.get("/plants", params={"q": "Curcuma longa"})
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["plant_id"] == str(ids["p1"]))
    assert row["compound_count"] == 2


@pytest.mark.asyncio
async def test_plant_full_list_has_zero_count_for_plant_without_compounds(alias_client) -> None:
    c, ids = alias_client
    resp = await c.get("/plants")  # empty q -> full list
    assert resp.status_code == 200
    by_id = {r["plant_id"]: r for r in resp.json()}
    assert by_id[str(ids["p3"])]["compound_count"] == 0  # Allium sativum: no plant_compounds


@pytest.mark.asyncio
async def test_disease_search_includes_target_count(alias_client) -> None:
    c, ids = alias_client
    resp = await c.get("/diseases", params={"q": "Type 2 Diabetes"})
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["disease_id"] == str(ids["d1"]))
    assert row["target_count"] == 2  # unfiltered total (both 0.9 and 0.4 counted)


@pytest.mark.asyncio
async def test_disease_full_list_has_zero_count_for_disease_without_targets(alias_client) -> None:
    c, ids = alias_client
    resp = await c.get("/diseases")
    assert resp.status_code == 200
    by_id = {r["disease_id"]: r for r in resp.json()}
    assert by_id[str(ids["d2"])]["target_count"] == 0  # Alzheimer: no disease_targets seeded
