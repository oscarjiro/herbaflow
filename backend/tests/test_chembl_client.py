import httpx
import pytest

from app.errors import ServiceUnavailableError
from app.integrations.chembl import ChemblClient


@pytest.mark.asyncio
async def test_filters_by_pchembl_confidence_human_and_type(httpx_mock):
    httpx_mock.add_response(
        json={
            "activities": [
                {
                    "pchembl_value": "6.5",
                    "standard_type": "IC50",
                    "target_organism": "Homo sapiens",
                    "target_confidence_score": 9,
                    "target_components": [{"accession": "P04637"}],
                },
                {
                    "pchembl_value": "3.0",
                    "standard_type": "IC50",
                    "target_organism": "Homo sapiens",
                    "target_confidence_score": 9,
                    "target_components": [{"accession": "Q00000"}],
                },
                {
                    "pchembl_value": "7.0",
                    "standard_type": "IC50",
                    "target_organism": "Mus musculus",
                    "target_confidence_score": 9,
                    "target_components": [{"accession": "P11111"}],
                },
                {
                    "pchembl_value": None,
                    "standard_type": "IC50",
                    "target_organism": "Homo sapiens",
                    "target_confidence_score": 9,
                    "target_components": [{"accession": "P22222"}],
                },
            ],
            "page_meta": {"next": None},
        }
    )
    async with httpx.AsyncClient() as c:
        hits = await ChemblClient(c).targets_for_inchikey("AAA", min_pchembl=5.0, min_confidence=7)
    accs = {h.uniprot_accession for h in hits}
    assert accs == {"P04637"}
    assert hits[0].pchembl_value == 6.5


@pytest.mark.asyncio
async def test_outage_raises_service_unavailable(httpx_mock):
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(status_code=503)
    async with httpx.AsyncClient() as c:
        with pytest.raises(ServiceUnavailableError):
            await ChemblClient(c).targets_for_inchikey("AAA", min_pchembl=5.0, min_confidence=7)
