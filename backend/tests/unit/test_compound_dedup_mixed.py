"""Regression guard: same molecule in two different input formats dedupes to one compound.

Verifies that submitting "quercetin" (name/SMILES-treated) and "5280343" (CID string)
collapses to a single unique compound because both resolve — via PubChem — to the same
InChIKey (REFJWTPEDVJJIY-UHFFFAOYSA-N) and therefore to the same deterministic
compound_id (UUID v5).

HTTP call sequence for validate_compound on EACH input:
  Call 1: POST /compound/smiles/cids/JSON  (data={"smiles": <raw_input>})
          → {"IdentifierList": {"CID": [5280343]}}
  Call 2: GET  /compound/cid/5280343/property/{PROPERTY_LIST}/JSON
          → {"PropertyTable": {"Properties": [...]}}

Both inputs follow the same two-call path because neither starts with "InChI=",
so _fetch_cid always routes them through the SMILES POST endpoint.

Total: 4 responses registered — 2 inputs × (1 POST + 1 GET).
pytest-httpx strict accounting (default) guarantees every registered response
is consumed and no unmatched request goes undetected.
"""
from __future__ import annotations

import pytest
import httpx

from app.services.compound_dedup import deduplicate_compounds

QUERCETIN_IK = "REFJWTPEDVJJIY-UHFFFAOYSA-N"
QUERCETIN_CID = 5280343

_SMILES_CID_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/cids/JSON"
_PROPERTY_URL = (
    f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{QUERCETIN_CID}"
    "/property/IUPACName,MolecularWeight,MolecularFormula,"
    "InChIKey,XLogP,HBondDonorCount,HBondAcceptorCount,RotatableBondCount/JSON"
)

_CIDS_RESPONSE = {"IdentifierList": {"CID": [QUERCETIN_CID]}}

_PROPS_RESPONSE = {
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


@pytest.mark.asyncio
async def test_same_molecule_two_formats_dedupes(httpx_mock):
    """A name-string and a CID-string for the same molecule must collapse to one unique.

    Structural guarantees (non-vacuous):

    1. Strict mock accounting (pytest-httpx default): every registered response
       must be consumed, and any unmatched request raises an error.  Removing
       any of the 4 registrations causes validate_compound to fail for that
       input, which triggers the string-fallback path — the two different raw
       strings ("quercetin", "5280343") produce TWO distinct fallback keys,
       making len(unique_new) == 2 and breaking the len == 1 assertion.

    2. The assert len(duplicates) == 1 confirms the second input was flagged
       as a within-batch duplicate, not silently dropped or put in a third bucket.

    3. The assert unique_new[0] == "quercetin" pins which input wins by position
       (first occurrence), so a future change that swaps the order would fail.

    4. The POST match_data bindings ensure the correct SMILES body was sent for
       each input — wrong body ⇒ no match ⇒ strict accounting fails.
    """
    # --- Register exactly 4 responses, each bound to its specific request ---

    # Input 1: "quercetin" — POST CID resolution (body: application/x-www-form-urlencoded)
    httpx_mock.add_response(
        method="POST",
        url=_SMILES_CID_URL,
        match_content=b"smiles=quercetin",
        json=_CIDS_RESPONSE,
    )
    # Input 1: "quercetin" — GET property fetch
    httpx_mock.add_response(
        method="GET",
        url=_PROPERTY_URL,
        json=_PROPS_RESPONSE,
    )

    # Input 2: "5280343" — POST CID resolution (body: application/x-www-form-urlencoded)
    httpx_mock.add_response(
        method="POST",
        url=_SMILES_CID_URL,
        match_content=b"smiles=5280343",
        json=_CIDS_RESPONSE,
    )
    # Input 2: "5280343" — GET property fetch (same URL; consumed second by registration order)
    httpx_mock.add_response(
        method="GET",
        url=_PROPERTY_URL,
        json=_PROPS_RESPONSE,
    )

    async with httpx.AsyncClient() as client:
        unique_new, duplicates = await deduplicate_compounds(
            submitted=["quercetin", "5280343"],
            existing_ids=set(),
            client=client,
        )

    # Both inputs resolved via PubChem to the same compound_id — dedup collapses them.
    assert len(unique_new) == 1, (
        f"Expected 1 unique compound, got {len(unique_new)}: {unique_new}. "
        "Both inputs must resolve to the same compound_id via PubChem."
    )
    assert len(duplicates) == 1, (
        f"Expected 1 duplicate, got {len(duplicates)}: {duplicates}. "
        "The second input must be flagged as a within-batch duplicate."
    )
    # First input wins by position; second is the duplicate.
    assert unique_new[0] == "quercetin", (
        "First input 'quercetin' must be the unique compound (wins by position)."
    )
    assert duplicates[0] == "5280343", (
        "Second input '5280343' must be the within-batch duplicate."
    )
