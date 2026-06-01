"""Test that validate_compound emits ETL-aligned compound_id and canonical_key.

Verifies that the pubchem_compound integration uses the shared canonicalization
core (app.services.canonicalize) rather than its own divergent UUID scheme.

HTTP call sequence for validate_compound("O=c1c(O)c(...)oc2cc(O)cc(O)c12", client):
  Call 1: POST /compound/smiles/cids/JSON  (data={"smiles": <input>})
          → {"IdentifierList": {"CID": [5280343]}}
  Call 2: GET  /compound/cid/5280343/property/{PROPERTY_LIST}/JSON
          → {"PropertyTable": {"Properties": [...]}}
Both calls are mocked below — if either is missing, validate_compound returns None
and the result-is-not-None guard catches it immediately.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from integrations.pubchem_compound import validate_compound
from app.services.canonicalize import make_compound_id, compound_canonical_key

QUERCETIN_IK = "REFJWTPEDVJJIY-UHFFFAOYSA-N"
QUERCETIN_CID = 5280343
QUERCETIN_SMILES = "O=c1c(O)c(-c2ccc(O)c(O)c2)oc2cc(O)cc(O)c12"

_QUERCETIN_CIDS = {"IdentifierList": {"CID": [QUERCETIN_CID]}}

_QUERCETIN_PROPERTIES = {
    "PropertyTable": {
        "Properties": [
            {
                "CID": QUERCETIN_CID,
                "IUPACName": "2-(3,4-dihydroxyphenyl)-3,5,7-trihydroxychromen-4-one",
                "MolecularFormula": "C15H10O7",
                "MolecularWeight": 302.24,
                "InChIKey": QUERCETIN_IK,
                "XLogP": 1.5,
                "HBondDonorCount": 5,
                "HBondAcceptorCount": 7,
                "RotatableBondCount": 1,
            }
        ]
    }
}


def _make_response(data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


@pytest.mark.asyncio
async def test_validate_compound_emits_etl_aligned_identity():
    """validate_compound must produce an id and canonical_key that match the shared core.

    Non-vacuous guards: the mock drives BOTH HTTP calls (POST for CID lookup,
    GET for property fetch). If either mock is missing, validate_compound returns
    None and the first assert catches it. The inchikey and pubchem_cid asserts
    confirm the result is populated from the mocked data, not a fallback.
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    # Call 1: CID resolution — POST /compound/smiles/cids/JSON
    mock_client.post = AsyncMock(return_value=_make_response(_QUERCETIN_CIDS))
    # Call 2: property fetch — GET /compound/cid/5280343/property/.../JSON
    mock_client.get = AsyncMock(return_value=_make_response(_QUERCETIN_PROPERTIES))

    result = await validate_compound(QUERCETIN_SMILES, mock_client)

    # Guard 1: result must not be None — proves both HTTP calls were satisfied
    assert result is not None

    # Guard 2: data actually came from the mocked responses, not a fallback value
    assert result["inchikey"] == QUERCETIN_IK
    assert result["pubchem_cid"] == str(QUERCETIN_CID)  # "5280343" as string

    # Guard 3: both HTTP legs were exercised (POST for CID, GET for properties)
    mock_client.post.assert_called_once()
    mock_client.get.assert_called_once()

    # Identity asserts: compound_id and canonical_key must be ETL-aligned
    assert result["compound_id"] == make_compound_id(QUERCETIN_IK)
    assert result["compound_id"] == "21d75a4d-8ff2-527e-876c-ba5ef28a68e8"
    # canonical_key must be present and ETL-aligned
    assert result["canonical_key"] == compound_canonical_key(QUERCETIN_IK)
    assert result["canonical_key"] == "inchikey:REFJWTPEDVJJIY-UHFFFAOYSA-N"
