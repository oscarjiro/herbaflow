"""Unit tests for integrations/pubchem_compound.py (T4.3).

Tests PubChem validation and ADME computation without real HTTP calls.
Uses unittest.mock to mock httpx responses (avoids pytest-httpx loop-scope issues).
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from integrations.pubchem_compound import (
    validate_compound,
    compute_adme,
    make_compound_id,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ASPIRIN_SMILES = "CC(=O)Oc1ccccc1C(=O)O"
_ASPIRIN_INCHI = "InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)"
_ASPIRIN_INCHIKEY = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"

_PUBCHEM_PROPERTIES = {
    "PropertyTable": {
        "Properties": [
            {
                "CID": 2244,
                "IUPACName": "2-acetoxybenzoic acid",
                "MolecularFormula": "C9H8O4",
                "MolecularWeight": 180.16,
                "InChIKey": _ASPIRIN_INCHIKEY,
                "XLogP": 1.2,
                "HBondDonorCount": 1,
                "HBondAcceptorCount": 4,
                "RotatableBondCount": 3,
            }
        ]
    }
}


def _make_response(data: dict, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response that returns json-encoded data."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _make_404() -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    resp.raise_for_status.return_value = None
    resp.json.return_value = {}
    return resp


# ---------------------------------------------------------------------------
# Test 1: SMILES validation → valid compound → returns compound dict with compound_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_smiles_validation_valid_compound():
    """A valid SMILES string resolves to a compound dict with expected fields."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=_make_response(_PUBCHEM_PROPERTIES))

    result = await validate_compound(_ASPIRIN_SMILES, mock_client)

    assert result is not None
    assert result["inchikey"] == _ASPIRIN_INCHIKEY
    assert result["iupac_name"] == "2-acetoxybenzoic acid"
    assert result["molecular_formula"] == "C9H8O4"
    assert abs(result["molecular_weight"] - 180.16) < 0.01
    assert result["canonical_name"] == "2-acetoxybenzoic acid"
    assert result["plant_ids"] == []
    # compound_id must be a deterministic UUID v5
    assert result["compound_id"] == make_compound_id(_ASPIRIN_INCHIKEY)
    # ADME fields present
    assert "adme_pass" in result
    assert "lipinski_pass" in result
    assert result["lipinski_pass"] is True  # MW=180, XLogP=1.2, HBD=1, HBA=4 → pass


# ---------------------------------------------------------------------------
# Test 2: InChI validation → valid compound → returns compound dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inchi_validation_valid_compound():
    """A valid InChI string resolves to a compound dict (uses POST for InChI inputs)."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_make_response(_PUBCHEM_PROPERTIES))

    result = await validate_compound(_ASPIRIN_INCHI, mock_client)

    assert result is not None
    assert result["inchikey"] == _ASPIRIN_INCHIKEY
    assert result["compound_id"] == make_compound_id(_ASPIRIN_INCHIKEY)
    assert result["lipinski_pass"] is True
    # Confirm POST was called (InChI path), not GET
    mock_client.post.assert_called_once()
    mock_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: HTTP 404 → compound marked as failed (returns None)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_http_404_returns_none():
    """A 404 response from PubChem means the compound is invalid — returns None."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=_make_404())

    result = await validate_compound("not_a_real_smiles", mock_client)

    assert result is None


# ---------------------------------------------------------------------------
# Test 4: ADME computation → Lipinski pass for MW=300, XLogP=2, HBD=1, HBA=3
# ---------------------------------------------------------------------------

def test_compute_adme_lipinski_pass():
    """Within Lipinski limits → lipinski_pass=True, adme_pass=True."""
    props = {
        "MolecularWeight": 300.0,
        "XLogP": 2.0,
        "HBondDonorCount": 1,
        "HBondAcceptorCount": 3,
        "RotatableBondCount": 4,
    }
    result = compute_adme(props)

    assert result["lipinski_pass"] is True
    assert result["adme_pass"] is True
    assert result["mw"] == 300.0
    assert result["xlogp"] == 2.0
    assert result["hbd"] == 1
    assert result["hba"] == 3
    assert result["rotatable_bonds"] == 4


# ---------------------------------------------------------------------------
# Test 5: ADME computation → Lipinski fail for MW=600
# ---------------------------------------------------------------------------

def test_compute_adme_lipinski_fail_heavy():
    """MW > 500 → lipinski_pass=False, adme_pass=False."""
    props = {
        "MolecularWeight": 600.0,
        "XLogP": 2.0,
        "HBondDonorCount": 1,
        "HBondAcceptorCount": 3,
        "RotatableBondCount": 4,
    }
    result = compute_adme(props)

    assert result["lipinski_pass"] is False
    assert result["adme_pass"] is False
    assert result["mw"] == 600.0


# ---------------------------------------------------------------------------
# Test 6: ADME computation → Lipinski fail for XLogP > 5
# ---------------------------------------------------------------------------

def test_compute_adme_lipinski_fail_logp():
    """XLogP > 5 → lipinski_pass=False."""
    props = {
        "MolecularWeight": 300.0,
        "XLogP": 6.0,
        "HBondDonorCount": 1,
        "HBondAcceptorCount": 3,
        "RotatableBondCount": 4,
    }
    result = compute_adme(props)

    assert result["lipinski_pass"] is False
    assert result["adme_pass"] is False


# ---------------------------------------------------------------------------
# Test 7: String properties (as returned by PubChem REST API) — must coerce
# ---------------------------------------------------------------------------

def test_compute_adme_string_properties():
    """PubChem REST API returns numeric values as strings — must coerce before comparison."""
    props = {
        "MolecularWeight": "342.43",  # string, as returned by PubChem REST
        "XLogP": "3.2",
        "HBondDonorCount": "2",
        "HBondAcceptorCount": "5",
        "RotatableBondCount": "4",
    }
    result = compute_adme(props)
    assert result["lipinski_pass"] is True
    assert result["mw"] == pytest.approx(342.43)


# ---------------------------------------------------------------------------
# Test 8: None properties — must return insufficient_data=True, not auto-pass
# ---------------------------------------------------------------------------

def test_compute_adme_none_properties():
    """When PubChem returns None for a property, result must be 'insufficient_data'."""
    props = {
        "MolecularWeight": None,
        "XLogP": None,
        "HBondDonorCount": None,
        "HBondAcceptorCount": None,
        "RotatableBondCount": None,
    }
    result = compute_adme(props)
    assert result["adme_pass"] is False
    assert result["insufficient_data"] is True


# ---------------------------------------------------------------------------
# Test 9: Failing Lipinski with string properties
# ---------------------------------------------------------------------------

def test_compute_adme_failing_lipinski():
    """Compound exceeding Lipinski rules must fail."""
    props = {
        "MolecularWeight": "600.0",
        "XLogP": "6.0",
        "HBondDonorCount": "3",
        "HBondAcceptorCount": "8",
        "RotatableBondCount": "5",
    }
    result = compute_adme(props)
    assert result["lipinski_pass"] is False
    assert result["adme_pass"] is False
