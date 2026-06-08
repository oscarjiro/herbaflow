import pytest


@pytest.mark.asyncio
async def test_auto_run_completes(client) -> None:
    c, ids = client
    resp = await c.post(
        "/analyses",
        json={"plant_ids": [str(ids["plant_full"])], "disease_id": str(ids["disease"])},
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    final = None
    for _ in range(50):
        poll = await c.get(f"/analyses/{run_id}")
        final = poll.json()
        if final["status"] in ("complete", "failed"):
            break
    assert final["status"] == "complete"
    assert final["stage_results"]["1"]["count"] == 2
    assert final["expires_at"] is not None


@pytest.mark.asyncio
async def test_guided_pauses_then_advances(client) -> None:
    c, ids = client
    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_full"])],
            "disease_id": str(ids["disease"]),
            "mode": "guided",
        },
    )
    run_id = resp.json()["analysis_id"]

    status = None
    for _ in range(50):
        status = (await c.get(f"/analyses/{run_id}")).json()["status"]
        if status == "stage_1_awaiting_approval":
            break
    assert status == "stage_1_awaiting_approval"

    adv = await c.post(f"/analyses/{run_id}/advance")
    assert adv.status_code == 200
    assert adv.json()["status"] == "complete"


@pytest.mark.asyncio
async def test_zero_compounds_fails(client) -> None:
    c, ids = client
    resp = await c.post(
        "/analyses",
        json={"plant_ids": [str(ids["plant_empty"])], "disease_id": str(ids["disease"])},
    )
    run_id = resp.json()["analysis_id"]
    final = None
    for _ in range(50):
        final = (await c.get(f"/analyses/{run_id}")).json()
        if final["status"] in ("complete", "failed"):
            break
    assert final["status"] == "failed"
    assert "compound" in final["error_message"].lower()


@pytest.mark.asyncio
async def test_unknown_plant_is_422(client) -> None:
    import uuid

    c, ids = client
    resp = await c.post(
        "/analyses",
        json={"plant_ids": [str(uuid.uuid4())], "disease_id": str(ids["disease"])},
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_diseases_and_plants_list(client) -> None:
    c, ids = client
    assert (await c.get("/diseases")).status_code == 200
    plants = await c.get("/plants")
    assert plants.status_code == 200
    assert len(plants.json()) == 2
