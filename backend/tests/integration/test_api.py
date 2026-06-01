import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_list_diseases_returns_10(client):
    resp = await client.get("/diseases")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 10  # 10 curated diseases from ETL


async def test_list_plants_has_compounds(client):
    resp = await client.get("/plants")
    assert resp.status_code == 200
    plants = resp.json()
    assert len(plants) > 0
    # At least one plant should have compounds
    assert any(p["compound_count"] > 0 for p in plants)


async def test_create_analysis_returns_pending(client):
    # Get a real plant_id to use
    plants_resp = await client.get("/plants?limit=1")
    plant_id = plants_resp.json()[0]["plant_id"]

    diseases_resp = await client.get("/diseases")
    disease_id = diseases_resp.json()[0]["disease_id"]

    resp = await client.post("/analyses", json={
        "name": "Integration Test Run",
        "mode": "guided",
        "plant_ids": [plant_id],
        "disease_id": disease_id,
        "parameters": {},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert "analysis_id" in data


# ── Plant detail ───────────────────────────────────────────────────────────────

async def test_get_plant_detail(client):
    plants_resp = await client.get("/plants")
    plant = plants_resp.json()[0]

    resp = await client.get(f"/plants/{plant['plant_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plant_id"] == plant["plant_id"]
    assert "compound_count" in data
    assert "canonical_scientific_name" in data


async def test_get_plant_404(client):
    resp = await client.get("/plants/pl_nonexistent_xyz_000")
    assert resp.status_code == 404


async def test_get_plant_compounds(client):
    plants_resp = await client.get("/plants")
    plant_id = plants_resp.json()[0]["plant_id"]

    resp = await client.get(f"/plants/{plant_id}/compounds")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── Compound list and detail ───────────────────────────────────────────────────

async def test_list_compounds(client):
    resp = await client.get("/compounds")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


async def test_list_compounds_with_limit(client):
    resp = await client.get("/compounds?limit=5")
    assert resp.status_code == 200
    assert len(resp.json()) <= 5


async def test_list_compounds_filter_has_chembl(client):
    resp = await client.get("/compounds?has_chembl=true")
    assert resp.status_code == 200
    data = resp.json()
    assert all("chembl_id" in c and c["chembl_id"] is not None for c in data)


async def test_get_compound_detail(client):
    compounds_resp = await client.get("/compounds?limit=1")
    compound_id = compounds_resp.json()[0]["compound_id"]

    resp = await client.get(f"/compounds/{compound_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["compound_id"] == compound_id
    assert "molecular_weight" in data


async def test_get_compound_404(client):
    resp = await client.get("/compounds/al_nonexistent_xyz_000")
    assert resp.status_code == 404


# ── Disease detail ─────────────────────────────────────────────────────────────

async def test_get_disease_detail(client):
    diseases_resp = await client.get("/diseases")
    disease_id = diseases_resp.json()[0]["disease_id"]

    resp = await client.get(f"/diseases/{disease_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["disease_id"] == disease_id
    assert "disease_name" in data


async def test_get_disease_404(client):
    resp = await client.get("/diseases/dis_nonexistent_xyz_000")
    assert resp.status_code == 404


# ── Analyses: list, detail, status ────────────────────────────────────────────

async def test_list_analyses(client):
    resp = await client.get("/analyses")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_analysis_detail(client):
    plants_resp = await client.get("/plants?limit=1")
    plant_id = plants_resp.json()[0]["plant_id"]
    disease_id = (await client.get("/diseases")).json()[0]["disease_id"]

    create_resp = await client.post("/analyses", json={
        "name": "Detail Test",
        "mode": "guided",
        "plant_ids": [plant_id],
        "disease_id": disease_id,
        "parameters": {},
    })
    assert create_resp.status_code == 201
    analysis_id = create_resp.json()["analysis_id"]

    resp = await client.get(f"/analyses/{analysis_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_id"] == analysis_id
    assert "stage_results" in data
    assert "mode" in data


async def test_get_analysis_status(client):
    plants_resp = await client.get("/plants?limit=1")
    plant_id = plants_resp.json()[0]["plant_id"]
    disease_id = (await client.get("/diseases")).json()[0]["disease_id"]

    create_resp = await client.post("/analyses", json={
        "name": "Status Test",
        "mode": "guided",
        "plant_ids": [plant_id],
        "disease_id": disease_id,
        "parameters": {},
    })
    analysis_id = create_resp.json()["analysis_id"]

    resp = await client.get(f"/analyses/{analysis_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "progress" in data
    assert data["progress"]["total"] == 8


async def test_get_analysis_404(client):
    resp = await client.get("/analyses/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Analyses: approve returns 400 when not awaiting ───────────────────────────

async def test_approve_when_not_awaiting_returns_400(client):
    plants_resp = await client.get("/plants?limit=1")
    plant_id = plants_resp.json()[0]["plant_id"]
    disease_id = (await client.get("/diseases")).json()[0]["disease_id"]

    create_resp = await client.post("/analyses", json={
        "name": "Approve 400 Test",
        "mode": "guided",
        "plant_ids": [plant_id],
        "disease_id": disease_id,
        "parameters": {},
    })
    analysis_id = create_resp.json()["analysis_id"]
    # Reject stage 1 (status → stage_1_rejected, not awaiting)
    reject_resp = await client.post(f"/analyses/{analysis_id}/reject")
    assert reject_resp.status_code == 200
    # Now status is stage_1_rejected — approve should return 400
    resp = await client.post(f"/analyses/{analysis_id}/approve")
    assert resp.status_code == 400


# ── Analyses: delete ───────────────────────────────────────────────────────────

async def test_delete_analysis(client):
    plants_resp = await client.get("/plants?limit=1")
    plant_id = plants_resp.json()[0]["plant_id"]
    disease_id = (await client.get("/diseases")).json()[0]["disease_id"]

    create_resp = await client.post("/analyses", json={
        "name": "Delete Test",
        "mode": "guided",
        "plant_ids": [plant_id],
        "disease_id": disease_id,
        "parameters": {},
    })
    analysis_id = create_resp.json()["analysis_id"]

    del_resp = await client.delete(f"/analyses/{analysis_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # Verify gone
    get_resp = await client.get(f"/analyses/{analysis_id}")
    assert get_resp.status_code == 404


# ── Analyses: reject returns 400 when not awaiting ────────────────────────────

async def test_reject_when_not_awaiting_returns_400(client):
    plants_resp = await client.get("/plants?limit=1")
    plant_id = plants_resp.json()[0]["plant_id"]
    disease_id = (await client.get("/diseases")).json()[0]["disease_id"]

    create_resp = await client.post("/analyses", json={
        "name": "Reject 400 Test",
        "mode": "guided",
        "plant_ids": [plant_id],
        "disease_id": disease_id,
        "parameters": {},
    })
    analysis_id = create_resp.json()["analysis_id"]
    # First reject succeeds (stage_1_awaiting_approval → stage_1_rejected)
    first_reject = await client.post(f"/analyses/{analysis_id}/reject")
    assert first_reject.status_code == 200
    # Second reject should return 400 — status is stage_1_rejected, not awaiting
    resp = await client.post(f"/analyses/{analysis_id}/reject")
    assert resp.status_code == 400


# ── Analyses: export stage not yet run returns 404 ────────────────────────────

async def test_export_stage_not_run_returns_404(client):
    plants_resp = await client.get("/plants?limit=1")
    plant_id = plants_resp.json()[0]["plant_id"]
    disease_id = (await client.get("/diseases")).json()[0]["disease_id"]

    create_resp = await client.post("/analyses", json={
        "name": "Export 404 Test",
        "mode": "guided",
        "plant_ids": [plant_id],
        "disease_id": disease_id,
        "parameters": {},
    })
    analysis_id = create_resp.json()["analysis_id"]

    # No stages have run, so stage_8 results don't exist
    resp = await client.get(f"/analyses/{analysis_id}/export/8")
    assert resp.status_code == 404


# ── Validation error ───────────────────────────────────────────────────────────

async def test_create_analysis_missing_fields_returns_422(client):
    resp = await client.post("/analyses", json={})
    assert resp.status_code == 422
