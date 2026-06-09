import httpx
import pytest

from app.integrations.pubchem import PubChemClient


@pytest.mark.asyncio
async def test_fetch_by_inchikey_reads_new_field_names(httpx_mock) -> None:
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
    async with httpx.AsyncClient() as client:
        rec = await PubChemClient(client).fetch_by_inchikey("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
    assert rec is not None
    assert rec.pubchem_cid == "702"
    assert rec.smiles == "CCO"  # prefers stereo-bearing SMILES
    assert rec.molecular_formula == "C2H6O"


@pytest.mark.asyncio
async def test_fetch_by_inchikey_404_returns_none(httpx_mock) -> None:
    httpx_mock.add_response(status_code=404)
    async with httpx.AsyncClient() as client:
        assert await PubChemClient(client).fetch_by_inchikey("ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-Z") is None
