# backend/tests/integration/test_create_idempotency.py

# The integration `client` fixture (conftest.py) yields a TUPLE: (httpx AsyncClient, seeded ids).
# There is NO `selection_payload` fixture — build a minimal valid AnalysisCreate body inline from
# the seeded plant + disease (mirrors test_guided_machinery._create). Create returns 202 with key
# `analysis_id`. asyncio_mode="auto", so bare `async def test_...` needs no marker.


def _body(ids) -> dict:
    return {
        "plant_ids": [str(ids["plant_full"])],
        "disease_id": str(ids["disease"]),
        "mode": "guided",
    }


async def test_same_key_returns_same_run(client) -> None:
    c, ids = client
    h = {"Idempotency-Key": "11111111-1111-1111-1111-111111111111"}
    r1 = await c.post("/analyses", json=_body(ids), headers=h)
    r2 = await c.post("/analyses", json=_body(ids), headers=h)
    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json()["analysis_id"] == r2.json()["analysis_id"]


async def test_different_key_creates_new_run(client) -> None:
    c, ids = client
    r1 = await c.post("/analyses", json=_body(ids), headers={"Idempotency-Key": "key-a"})
    r2 = await c.post("/analyses", json=_body(ids), headers={"Idempotency-Key": "key-b"})
    assert r1.json()["analysis_id"] != r2.json()["analysis_id"]


async def test_no_key_creates_new_run_each_time(client) -> None:
    c, ids = client
    r1 = await c.post("/analyses", json=_body(ids))
    r2 = await c.post("/analyses", json=_body(ids))
    assert r1.json()["analysis_id"] != r2.json()["analysis_id"]
