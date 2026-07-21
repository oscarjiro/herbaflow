import pytest

_SETTLED = frozenset(
    {
        "complete",
        "failed",
        "stage_1_awaiting_approval",
        "stage_2_awaiting_approval",
        "stage_3_awaiting_approval",
    }
)


async def _poll(c, run_id: str, *, until: str | None = None, max_iters: int = 80) -> str:
    """Poll GET /analyses/{id} for the run status until ``until`` (or any settled status)."""
    status = ""
    for _ in range(max_iters):
        status = (await c.get(f"/analyses/{run_id}")).json()["status"]
        if until is not None and status == until:
            break
        if until is None and status in _SETTLED:
            break
    return status


@pytest.mark.asyncio
async def test_auto_run_hard_stops_on_empty_targets(client) -> None:
    """An auto run executes S1 + S2, then hard-stops at the empty S3 (the seeded compounds
    have no findable targets) — don't-waste-downstream. S1/S2 still ran correctly."""
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
    assert final["status"] == "failed"
    assert "step 3" in final["error_message"].lower()
    assert final["stage_results"]["1"]["count"] == 2
    assert final["stage_results"]["2"]["count"] == 2


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

    assert await _poll(c, run_id, until="stage_1_awaiting_approval") == "stage_1_awaiting_approval"

    # advance is now non-blocking: 202 + the *_running start state; the stage runs in a
    # BackgroundTask, so the settled status is read via a follow-up GET (poll), not the body.
    adv1 = await c.post(f"/analyses/{run_id}/advance")
    assert adv1.status_code == 202
    assert adv1.json()["status"] == "stage_2_running"
    assert await _poll(c, run_id, until="stage_2_awaiting_approval") == "stage_2_awaiting_approval"

    # Stage 3 runs with the seeded compounds (no InChIKey -> coverage 0) and pauses
    # at the guided S3 checkpoint.
    adv2 = await c.post(f"/analyses/{run_id}/advance")
    assert adv2.status_code == 202
    assert adv2.json()["status"] == "stage_3_running"
    assert await _poll(c, run_id, until="stage_3_awaiting_approval") == "stage_3_awaiting_approval"

    # Stage 3 is empty in this env (seeded compounds have no findable targets), so the guided
    # checkpoint now refuses Approve & Continue (blocking-stop): advancing returns 409 and the
    # run stays parked at the S3 checkpoint.
    adv3 = await c.post(f"/analyses/{run_id}/advance")
    assert adv3.status_code == 409
    assert (await c.get(f"/analyses/{run_id}")).json()["status"] == "stage_3_awaiting_approval"


@pytest.mark.asyncio
async def test_zero_compounds_fails(client) -> None:
    c, ids = client
    # Explicitly auto: an empty Stage 1 hard-stops. The contract default is guided, which parks at
    # the Stage-1 checkpoint instead of failing, so the mode has to be stated to test this path.
    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_empty"])],
            "disease_id": str(ids["disease"]),
            "mode": "auto",
        },
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
async def test_selection_mode_forbids_manual_compound_ids_at_create(client) -> None:
    # plant selection mode + manual_compound_ids is now forbidden (schema 422).
    # Compounds are added/removed in Stage 1 after the run is created.
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
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_unknown_manual_compound_is_422(client) -> None:
    import uuid

    c, ids = client
    # manual_compounds mode with an unknown compound id → service rejects with 422.
    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_compounds",
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
