"""Unit tests for disease target_count on GET /diseases and GET /diseases/{id}.

Asserts that both endpoints expose target_count equal to the number of
disease_targets rows for each disease.
"""
from unittest.mock import AsyncMock, patch

from app.main import app
from app.models import Disease
from app.repositories import disease_repo
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DISEASE_ID_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DISEASE_ID_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def make_disease(disease_id: str, name: str) -> Disease:
    return Disease(
        disease_id=disease_id,
        canonical_key=f"doid:{disease_id[:4]}",
        disease_name=name,
        ontology_id=None,
        ontology_source=None,
    )


# ---------------------------------------------------------------------------
# list_diseases — target_count populated from bulk count
# ---------------------------------------------------------------------------


@patch.object(disease_repo, "get_aliases_by_disease_ids", new_callable=AsyncMock)
@patch.object(disease_repo, "count_targets_per_disease_bulk", new_callable=AsyncMock)
@patch.object(disease_repo, "list_diseases", new_callable=AsyncMock)
def test_list_diseases_exposes_target_count(
    mock_list,
    mock_counts,
    mock_aliases,
):
    """GET /diseases returns target_count = number of disease_targets rows per disease."""
    mock_list.return_value = [
        make_disease(DISEASE_ID_A, "Diabetes mellitus"),
        make_disease(DISEASE_ID_B, "Hypertension"),
    ]
    mock_counts.return_value = {DISEASE_ID_A: 5, DISEASE_ID_B: 3}
    mock_aliases.return_value = {}

    client = TestClient(app)
    response = client.get("/diseases")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    by_id = {d["disease_id"]: d for d in data}
    assert by_id[DISEASE_ID_A]["target_count"] == 5
    assert by_id[DISEASE_ID_B]["target_count"] == 3


@patch.object(disease_repo, "get_aliases_by_disease_ids", new_callable=AsyncMock)
@patch.object(disease_repo, "count_targets_per_disease_bulk", new_callable=AsyncMock)
@patch.object(disease_repo, "list_diseases", new_callable=AsyncMock)
def test_list_diseases_target_count_defaults_to_zero(
    mock_list,
    mock_counts,
    mock_aliases,
):
    """GET /diseases target_count defaults to 0 when disease has no disease_targets rows."""
    mock_list.return_value = [make_disease(DISEASE_ID_A, "Diabetes mellitus")]
    mock_counts.return_value = {}  # no rows for this disease
    mock_aliases.return_value = {}

    client = TestClient(app)
    response = client.get("/diseases")

    assert response.status_code == 200
    data = response.json()
    assert data[0]["target_count"] == 0


# ---------------------------------------------------------------------------
# get_disease — target_count populated from bulk count
# ---------------------------------------------------------------------------


@patch.object(disease_repo, "get_aliases_by_disease_ids", new_callable=AsyncMock)
@patch.object(disease_repo, "count_targets_per_disease_bulk", new_callable=AsyncMock)
@patch.object(disease_repo, "get_disease_by_id", new_callable=AsyncMock)
def test_get_disease_exposes_target_count(
    mock_get,
    mock_counts,
    mock_aliases,
):
    """GET /diseases/{id} returns target_count = number of disease_targets rows."""
    mock_get.return_value = make_disease(DISEASE_ID_A, "Diabetes mellitus")
    mock_counts.return_value = {DISEASE_ID_A: 12}
    mock_aliases.return_value = {}

    client = TestClient(app)
    response = client.get(f"/diseases/{DISEASE_ID_A}")

    assert response.status_code == 200
    data = response.json()
    assert data["target_count"] == 12


@patch.object(disease_repo, "get_aliases_by_disease_ids", new_callable=AsyncMock)
@patch.object(disease_repo, "count_targets_per_disease_bulk", new_callable=AsyncMock)
@patch.object(disease_repo, "get_disease_by_id", new_callable=AsyncMock)
def test_get_disease_target_count_defaults_to_zero(
    mock_get,
    mock_counts,
    mock_aliases,
):
    """GET /diseases/{id} target_count defaults to 0 when no disease_targets rows exist."""
    mock_get.return_value = make_disease(DISEASE_ID_A, "Diabetes mellitus")
    mock_counts.return_value = {}  # no rows for this disease
    mock_aliases.return_value = {}

    client = TestClient(app)
    response = client.get(f"/diseases/{DISEASE_ID_A}")

    assert response.status_code == 200
    data = response.json()
    assert data["target_count"] == 0
