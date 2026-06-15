# `client` yields (httpx AsyncClient, seeded ids). No `selection_payload` fixture — build inline.


def _body(ids) -> dict:
    return {
        "plant_ids": [str(ids["plant_full"])],
        "disease_id": str(ids["disease"]),
        "mode": "guided",
    }


async def test_delete_removes_run(client) -> None:
    c, ids = client
    created = await c.post("/analyses", json=_body(ids))
    rid = created.json()["analysis_id"]
    resp = await c.delete(f"/analyses/{rid}")
    assert resp.status_code == 204
    assert (await c.get(f"/analyses/{rid}")).status_code == 404


async def test_delete_missing_run_404(client) -> None:
    c, _ = client
    resp = await c.delete("/analyses/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.headers["content-type"] == "application/problem+json"
