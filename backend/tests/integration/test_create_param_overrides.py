# backend/tests/integration/test_create_param_overrides.py
#
# Integration tests for create-time advanced parameter overrides (POST /analyses).
# The `client` fixture (conftest.py) yields a tuple: (httpx AsyncClient, seeded ids).
# asyncio_mode="auto" — bare `async def test_...` needs no marker.

from app import contracts


def _body(ids, parameters=None) -> dict:
    body: dict = {
        "plant_ids": [str(ids["plant_full"])],
        "disease_id": str(ids["disease"]),
        "mode": "guided",
    }
    if parameters is not None:
        body["parameters"] = parameters
    return body


async def test_valid_overrides_reflected_in_stored_params(client) -> None:
    """Override two groups; verify the persisted run stores the overridden values."""
    c, ids = client
    overrides = {
        "ppi": {"min_confidence": 0.7},  # non-default tier (contract enum: 0.15/0.4/0.7/0.9)
        "enrichment": {"min_term_size": 10},  # non-default integer (default=5, min=1)
    }
    r = await c.post("/analyses", json=_body(ids, overrides))
    assert r.status_code == 202, r.text
    run = r.json()

    stored_params = run["parameters"]
    # Overridden values must be reflected.
    assert stored_params["ppi"]["min_confidence"] == 0.7
    assert stored_params["enrichment"]["min_term_size"] == 10
    # Untouched groups keep their contract defaults.
    assert stored_params["adme"] == contracts.adme_defaults()
    assert stored_params["target"] == contracts.target_defaults()
    assert stored_params["disease_targets"] == contracts.disease_targets_defaults()
    assert stored_params["hub_genes"] == contracts.hub_genes_defaults()
    # The touched groups keep all non-overridden keys at their defaults too.
    ppi_defaults = contracts.ppi_defaults()
    assert stored_params["ppi"]["max_proteins"] == ppi_defaults["max_proteins"]
    assert stored_params["ppi"]["allow_top_n_cap"] == ppi_defaults["allow_top_n_cap"]
    assert stored_params["ppi"]["network_type"] == ppi_defaults["network_type"]


async def test_out_of_bounds_returns_422_no_run_created(client) -> None:
    """A value exceeding the contract maximum → 422; no run is persisted."""
    c, ids = client
    # hub_genes.top_n has maximum=200; send 201 (max+1).
    overrides = {"hub_genes": {"top_n": 201}}
    r = await c.post("/analyses", json=_body(ids, overrides))
    assert r.status_code == 422, r.text
    # Confirm no run row was created for this request.
    data = r.json()
    assert "analysis_id" not in data


async def test_unknown_group_returns_422(client) -> None:
    """An unknown parameter group → 422."""
    c, ids = client
    r = await c.post("/analyses", json=_body(ids, {"bogus": {"x": 1}}))
    assert r.status_code == 422, r.text


async def test_unknown_key_within_valid_group_returns_422(client) -> None:
    """A valid group with an unknown parameter key → 422."""
    c, ids = client
    r = await c.post("/analyses", json=_body(ids, {"adme": {"no_such_param": 99}}))
    assert r.status_code == 422, r.text


async def test_no_parameters_gives_all_defaults(client) -> None:
    """Omitting parameters entirely → all six groups stored at their contract defaults."""
    c, ids = client
    r = await c.post("/analyses", json=_body(ids))
    assert r.status_code == 202, r.text
    stored = r.json()["parameters"]
    assert stored["adme"] == contracts.adme_defaults()
    assert stored["target"] == contracts.target_defaults()
    assert stored["disease_targets"] == contracts.disease_targets_defaults()
    assert stored["ppi"] == contracts.ppi_defaults()
    assert stored["hub_genes"] == contracts.hub_genes_defaults()
    assert stored["enrichment"] == contracts.enrichment_defaults()
