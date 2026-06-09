import pytest


@pytest.mark.asyncio
async def test_auto_run_completes(client) -> None:
    c, ids = client
    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_full"])],
            "disease_id": str(ids["disease"]),
            "mode": "auto",
        },
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
    assert final["stage_results"]["2"]["count"] == 2
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

    adv1 = await c.post(f"/analyses/{run_id}/advance")
    assert adv1.status_code == 200
    assert adv1.json()["status"] == "stage_2_awaiting_approval"

    # Stage 3 runs with the seeded compounds (no InChIKey -> coverage 0) and pauses
    # at the guided S3 checkpoint.
    adv2 = await c.post(f"/analyses/{run_id}/advance")
    assert adv2.status_code == 200
    assert adv2.json()["status"] == "stage_3_awaiting_approval"

    adv3 = await c.post(f"/analyses/{run_id}/advance")
    assert adv3.status_code == 200
    assert adv3.json()["status"] == "complete"


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
async def test_manual_compound_unions_into_stage1(client) -> None:
    c, ids = client
    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_empty"])],
            "disease_id": str(ids["disease"]),
            "mode": "auto",
            "manual_compound_ids": [str(ids["c1"])],
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    final = None
    for _ in range(50):
        final = (await c.get(f"/analyses/{run_id}")).json()
        if final["status"] in ("complete", "failed"):
            break
    assert final["status"] == "complete"
    assert final["stage_results"]["1"]["count"] == 1
    assert str(ids["c1"]) in final["stage_results"]["1"]["per_plant"]["manual"]
    assert final["stage_results"]["2"]["count"] == 1


@pytest.mark.asyncio
async def test_unknown_manual_compound_is_422(client) -> None:
    import uuid

    c, ids = client
    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_full"])],
            "disease_id": str(ids["disease"]),
            "manual_compound_ids": [str(uuid.uuid4())],
        },
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


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


@pytest.fixture
def non_mocked_hosts() -> list[str]:
    # Let the test's own ASGITransport calls (host "test") through; only PubChem is mocked.
    return ["test"]


@pytest.mark.asyncio
async def test_validate_enriches_persists_and_is_idempotent(client, httpx_mock) -> None:
    c, _ = client
    httpx_mock.add_response(
        url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/"
        "LFQSCWFLJHTTHZ-UHFFFAOYSA-N/property/"
        "MolecularFormula,MolecularWeight,SMILES,ConnectivitySMILES,IUPACName,CanonicalSMILES/JSON",
        json={
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 702,
                        "MolecularFormula": "C2H6O",
                        "MolecularWeight": "46.07",
                        "SMILES": "CCO",
                        "IUPACName": "ethanol",
                    }
                ]
            }
        },
    )

    first = await c.post("/compounds/validate", json={"inputs": [{"value": "CCO"}]})
    assert first.status_code == 200
    body = first.json()
    assert body["failed"] == []
    assert len(body["resolved"]) == 1
    assert body["resolved"][0]["validation_status"] == "externally_validated"
    compound_id = body["resolved"][0]["compound_id"]

    # Second call hits the DB first -> no PubChem request (no extra mock added).
    second = await c.post("/compounds/validate", json={"inputs": [{"value": "CCO"}]})
    assert second.status_code == 200
    repeat = second.json()
    assert len(repeat["resolved"]) == 1
    assert repeat["resolved"][0]["compound_id"] == compound_id


@pytest.mark.asyncio
async def test_validate_structure_only_on_pubchem_miss(client, httpx_mock) -> None:
    c, _ = client
    httpx_mock.add_response(status_code=404)

    resp = await c.post("/compounds/validate", json={"inputs": [{"value": "c1ccc(cc1)CCN"}]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == []
    assert len(body["resolved"]) == 1
    assert body["resolved"][0]["validation_status"] == "structure_only"


@pytest.mark.asyncio
async def test_validate_nowhere_inchikey_fails(client, httpx_mock) -> None:
    c, _ = client
    httpx_mock.add_response(status_code=404)

    resp = await c.post(
        "/compounds/validate",
        json={"inputs": [{"type": "inchikey", "value": "ZZZZZZZZZZZZZZ-UHFFFAOYSA-N"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolved"] == []
    assert len(body["failed"]) == 1
    assert "SMILES" in body["failed"][0]["reason"]
