"""Integration tests for GET /analyses (recent-runs list).

Uses the testcontainers Postgres fixture from conftest.py.
Seeded via the `client` fixture (httpx + seeded plants/disease).
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _body(ids: dict) -> dict:
    return {
        "plant_ids": [str(ids["plant_full"])],
        "disease_id": str(ids["disease"]),
        "mode": "guided",
    }


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty_returns_200_empty(client) -> None:
    """GET /analyses on an empty DB returns 200 with an empty list."""
    c, _ids = client
    resp = await c.get("/analyses")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_returns_created_run(client) -> None:
    """A just-created run appears in the list."""
    c, ids = client
    created = await c.post("/analyses", json=_body(ids))
    assert created.status_code == 202
    rid = created.json()["analysis_id"]

    resp = await c.get("/analyses")
    assert resp.status_code == 200
    items = resp.json()
    assert any(item["analysis_id"] == rid for item in items)


@pytest.mark.asyncio
async def test_list_newest_first(client) -> None:
    """Multiple runs come back newest-first."""
    c, ids = client
    r1 = (await c.post("/analyses", json=_body(ids))).json()["analysis_id"]
    r2 = (await c.post("/analyses", json=_body(ids))).json()["analysis_id"]
    r3 = (await c.post("/analyses", json=_body(ids))).json()["analysis_id"]

    resp = await c.get("/analyses")
    assert resp.status_code == 200
    items = resp.json()
    ids_in_order = [item["analysis_id"] for item in items]

    # r3 was created last — it must appear before r1 and r2
    assert ids_in_order.index(r3) < ids_in_order.index(r1)
    assert ids_in_order.index(r3) < ids_in_order.index(r2)


@pytest.mark.asyncio
async def test_list_limit_and_offset(client) -> None:
    """limit and offset page the list correctly."""
    c, ids = client
    for _ in range(5):
        await c.post("/analyses", json=_body(ids))

    page1 = (await c.get("/analyses", params={"limit": 2, "offset": 0})).json()
    page2 = (await c.get("/analyses", params={"limit": 2, "offset": 2})).json()

    assert len(page1) == 2
    assert len(page2) == 2
    # Pages must be disjoint
    ids1 = {i["analysis_id"] for i in page1}
    ids2 = {i["analysis_id"] for i in page2}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_list_clamped_limit(client) -> None:
    """limit > 100 is clamped to 100 (no error, response <= 100 items)."""
    c, ids = client
    resp = await c.get("/analyses", params={"limit": 9999})
    assert resp.status_code == 200
    assert len(resp.json()) <= 100


@pytest.mark.asyncio
async def test_list_item_has_no_stage_results(client) -> None:
    """Items in the list must not expose stage_results."""
    c, ids = client
    await c.post("/analyses", json=_body(ids))

    resp = await c.get("/analyses")
    assert resp.status_code == 200
    for item in resp.json():
        assert "stage_results" not in item


@pytest.mark.asyncio
async def test_list_item_carries_parameters(client) -> None:
    """Items carry the parameters dict (which holds input_modes / plant_ids)."""
    c, ids = client
    await c.post("/analyses", json=_body(ids))

    resp = await c.get("/analyses")
    assert resp.status_code == 200
    for item in resp.json():
        assert "parameters" in item
