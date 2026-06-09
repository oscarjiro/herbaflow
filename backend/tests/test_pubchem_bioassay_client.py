import httpx
import pytest

from app.integrations.pubchem_bioassay import PubChemBioAssayClient

_COLS = ["AID", "SID", "CID", "Activity Outcome", "Target Accession", "Assay Name"]


def _table(rows):
    return {"Table": {"Columns": {"Column": _COLS}, "Row": [{"Cell": c} for c in rows]}}


@pytest.mark.asyncio
async def test_active_with_accession_returned_and_deduped(httpx_mock):
    httpx_mock.add_response(
        json=_table(
            [
                ["1", "91276", "969516", "Inactive", "", "x"],
                ["2", "1", "969516", "Active", "P04637", "y"],
                ["3", "2", "969516", "Active", "", "z"],  # active, no accession -> skip
                ["4", "3", "969516", "Active", "p04637", "y"],  # dup (case) -> dedupe
                ["5", "4", "969516", "Unspecified", "Q00001", "w"],  # not active -> skip
            ]
        )
    )
    async with httpx.AsyncClient() as c:
        accs = await PubChemBioAssayClient(c).active_targets_for_inchikey("AAA")
    assert accs == ["P04637"]


@pytest.mark.asyncio
async def test_no_data_404_degrades_to_empty(httpx_mock):
    httpx_mock.add_response(status_code=404)
    async with httpx.AsyncClient() as c:
        accs = await PubChemBioAssayClient(c).active_targets_for_inchikey("AAA")
    assert accs == []


@pytest.mark.asyncio
async def test_outage_degrades_to_empty(httpx_mock):
    # raise_for_status is OUTSIDE _call, so the 503 is returned (not raised) by _call;
    # with_retry does not retry -> a single 503 response degrades to [].
    httpx_mock.add_response(status_code=503)
    async with httpx.AsyncClient() as c:
        accs = await PubChemBioAssayClient(c).active_targets_for_inchikey("AAA")
    assert accs == []
