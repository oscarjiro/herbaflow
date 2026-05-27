"""Unit tests for inject-compounds validation and user-compound add/remove endpoints.

Tests:
1. Empty compounds list → Pydantic ValidationError (min_length=1)
2. Compounds list exceeding 100 items → Pydantic ValidationError (max_length=100)
3. HTTP boundary: POST /analyses/{id}/inject-compounds with [] → HTTP 422
4. POST /analyses/{id}/user-compounds adds a compound to stage_1 results
5. DELETE /analyses/{id}/user-compounds/{compound_id} removes a compound from stage_1
"""
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.analysis import InjectCompoundsRequest

ANALYSIS_ID = "00000000-0000-0000-0000-000000000043"


# ---------------------------------------------------------------------------
# Test 1: Empty compounds list → ValidationError
# ---------------------------------------------------------------------------


def test_inject_compounds_empty_list_raises_validation_error():
    """InjectCompoundsRequest(compounds=[]) must raise a Pydantic ValidationError.

    The ``compounds`` field has min_length=1, so an empty list is rejected
    before the route handler runs.
    """
    with pytest.raises(ValidationError) as exc_info:
        InjectCompoundsRequest(compounds=[])

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("compounds",) for e in errors)


# ---------------------------------------------------------------------------
# Test 2: Over-limit compounds list → ValidationError
# ---------------------------------------------------------------------------


def test_inject_compounds_over_limit_raises_validation_error():
    """InjectCompoundsRequest with > 100 items must raise a Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        InjectCompoundsRequest(compounds=["CC"] * 101)

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("compounds",) for e in errors)


# ---------------------------------------------------------------------------
# Test 3: HTTP boundary — FastAPI translates Pydantic ValidationError → 422
# ---------------------------------------------------------------------------


def test_inject_compounds_http_empty_list_returns_422():
    """Sending compounds=[] over HTTP must produce a 422 response.

    This confirms FastAPI's request/response boundary: the Pydantic
    ValidationError from InjectCompoundsRequest (min_length=1) is
    automatically converted to HTTP 422 before the route handler runs.
    """
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/analyses/{ANALYSIS_ID}/inject-compounds",
        json={"compounds": []},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 4: POST /analyses/{id}/user-compounds adds a compound to stage_1
# ---------------------------------------------------------------------------

_ASPIRIN_SMILES = "CC(=O)Oc1ccccc1C(=O)O"
_MOCK_COMPOUND = {
    "compound_id": "11111111-1111-1111-1111-111111111111",
    "canonical_name": "aspirin",
    "inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
    "iupac_name": "2-(acetyloxy)benzoic acid",
    "molecular_formula": "C9H8O4",
    "molecular_weight": 180.16,
    "smiles": _ASPIRIN_SMILES,
    "logp": 1.2,
    "tpsa": 63.6,
    "hbond_donors": 1,
    "hbond_acceptors": 4,
    "rotatable_bonds": 3,
    "np_likeness_score": None,
    "lipinski_pass": True,
    "adme_pass": True,
    "is_pains_positive": False,
    "is_np_exception": False,
    "plant_ids": [],
}

_STAGE1_WITH_COMPOUND = {
    "compound_ids": ["11111111-1111-1111-1111-111111111111"],
    "compound_count": 1,
    "plant_ids": [],
    "total_compounds": 1,
    "plants_covered": 0,
    "compounds": [
        {
            "compound_id": "11111111-1111-1111-1111-111111111111",
            "canonical_name": "aspirin",
            "plant_ids": [],
        }
    ],
    "user_modified": True,
}


def _make_mock_run(stage1: dict | None = None):
    """Build a minimal mock AnalysisRun for unit tests."""
    run = MagicMock()
    run.stage_results = {"stage_1": stage1} if stage1 else {}
    run.status = "stage_1_awaiting_approval"
    return run


def test_add_user_compound_to_stage1():
    """POST /analyses/{id}/user-compounds adds a compound to stage_1 results."""
    mock_run = _make_mock_run()

    with (
        patch("app.repositories.analysis_repo.get_run", new=AsyncMock(return_value=mock_run)),
        patch("app.repositories.analysis_repo.update_run_status", new=AsyncMock()),
        patch(
            "integrations.pubchem_compound.validate_compound",
            new=AsyncMock(return_value=_MOCK_COMPOUND),
        ),
        patch("app.database.get_session"),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            f"/analyses/{ANALYSIS_ID}/user-compounds",
            json={"smiles": _ASPIRIN_SMILES},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["compound_id"] is not None
    assert data["canonical_name"] == "aspirin"


# ---------------------------------------------------------------------------
# Test 5: DELETE /analyses/{id}/user-compounds/{compound_id} removes it
# ---------------------------------------------------------------------------


def test_remove_user_compound_from_stage1():
    """DELETE /analyses/{id}/user-compounds/{compound_id} removes the compound."""
    mock_run = _make_mock_run(stage1=_STAGE1_WITH_COMPOUND)

    with (
        patch("app.repositories.analysis_repo.get_run", new=AsyncMock(return_value=mock_run)),
        patch("app.repositories.analysis_repo.update_run_status", new=AsyncMock()),
        patch("app.database.get_session"),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.delete(
            f"/analyses/{ANALYSIS_ID}/user-compounds/11111111-1111-1111-1111-111111111111",
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["removed"] == "11111111-1111-1111-1111-111111111111"
