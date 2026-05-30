"""Regression guard: same molecule in two different input formats dedupes to one compound.

Verifies that submitting "quercetin" (name) and "5280343" (CID string) together
collapses to a single unique compound because both resolve — via PubChem — to the
same InChIKey (REFJWTPEDVJJIY-UHFFFAOYSA-N) and therefore to the same
deterministic compound_id (UUID v5).

HTTP call sequence for validate_compound on EACH input:
  Call 1: POST /compound/smiles/cids/JSON  (data={"smiles": <raw_input>})
          → {"IdentifierList": {"CID": [5280343]}}
  Call 2: GET  /compound/cid/5280343/property/{PROPERTY_LIST}/JSON
          → {"PropertyTable": {"Properties": [...]}}

Both inputs follow the same two-call path because neither starts with "InChI=",
so _fetch_cid always routes them through the SMILES POST endpoint.
Total: 4 responses registered — 2 inputs × (1 POST + 1 GET).
"""
from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock

from app.services.compound_dedup import deduplicate_compounds

QUERCETIN_IK = "REFJWTPEDVJJIY-UHFFFAOYSA-N"
QUERCETIN_CID = 5280343

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
async def test_same_molecule_two_formats_dedupes():
    """A name and a CID for the same molecule must collapse to one unique compound.

    Non-vacuous guards:
    - 4 HTTP responses registered (2 per input: POST CID + GET props). Removing
      any one causes validate_compound to return None and the fallback path
      (string-based dedup) would produce 2 uniques (different raw strings), so
      the assert len(unique_new) == 1 would fail.
    - The assert len(duplicates) == 1 confirms the second input was recognized
      as a duplicate, not silently dropped.
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # Each input drives: POST (CID resolution) then GET (property fetch).
    # side_effect sequences the responses in call order.
    mock_client.post = AsyncMock(side_effect=[
        _make_response(_QUERCETIN_CIDS),   # POST for "quercetin"
        _make_response(_QUERCETIN_CIDS),   # POST for "5280343"
    ])
    mock_client.get = AsyncMock(side_effect=[
        _make_response(_QUERCETIN_PROPERTIES),  # GET props for "quercetin"
        _make_response(_QUERCETIN_PROPERTIES),  # GET props for "5280343"
    ])

    unique_new, duplicates = await deduplicate_compounds(
        submitted=["quercetin", "5280343"],
        existing_ids=set(),
        client=mock_client,
    )

    assert len(unique_new) == 1, (
        f"Expected 1 unique compound, got {len(unique_new)}: {unique_new}. "
        "Both inputs must resolve to the same compound_id via PubChem."
    )
    assert len(duplicates) == 1, (
        f"Expected 1 duplicate, got {len(duplicates)}: {duplicates}. "
        "The second input must be flagged as a within-batch duplicate."
    )
    assert unique_new[0] == "quercetin", "First input must be the unique (wins by position)"
    assert duplicates[0] == "5280343", "Second input must be the duplicate"

    # Confirm both inputs actually hit PubChem (not fallback string dedup)
    assert mock_client.post.call_count == 2, "Expected 2 POST calls (one per input)"
    assert mock_client.get.call_count == 2, "Expected 2 GET calls (one per input)"
