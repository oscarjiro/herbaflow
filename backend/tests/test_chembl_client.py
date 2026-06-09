import re

import httpx
import pytest

from app.errors import ServiceUnavailableError
from app.integrations.chembl import ChemblClient

_ACTIVITY_RE = re.compile(r".*/data/activity.*")
_ASSAY_RE = re.compile(r".*/data/assay.*")
_TARGET_RE = re.compile(r".*/data/target.*")


@pytest.mark.asyncio
async def test_join_filters_by_pchembl_confidence_human_and_type(httpx_mock):
    # /activity: one fully-qualifying, one below pchembl, one non-human, one whose
    # assay confidence is too low. accession/confidence are NOT on these rows.
    httpx_mock.add_response(
        url=_ACTIVITY_RE,
        json={
            "activities": [
                {
                    "pchembl_value": "6.5",
                    "standard_type": "IC50",
                    "target_organism": "Homo sapiens",
                    "target_tax_id": 9606,
                    "target_chembl_id": "CHEMBL_T1",
                    "assay_chembl_id": "CHEMBL_A1",
                },
                {
                    "pchembl_value": "3.0",
                    "standard_type": "IC50",
                    "target_organism": "Homo sapiens",
                    "target_tax_id": 9606,
                    "target_chembl_id": "CHEMBL_T3",
                    "assay_chembl_id": "CHEMBL_A3",
                },
                {
                    "pchembl_value": "7.0",
                    "standard_type": "IC50",
                    "target_organism": "Mus musculus",
                    "target_tax_id": 10090,
                    "target_chembl_id": "CHEMBL_T4",
                    "assay_chembl_id": "CHEMBL_A4",
                },
                {
                    "pchembl_value": "7.0",
                    "standard_type": "IC50",
                    "target_organism": "Homo sapiens",
                    "target_tax_id": 9606,
                    "target_chembl_id": "CHEMBL_T2",
                    "assay_chembl_id": "CHEMBL_A2",
                },
            ],
            "page_meta": {"next": None},
        },
    )
    # /assay: A1 passes (9), A2 fails (4). A3/A4 were dropped at step 1.
    httpx_mock.add_response(
        url=_ASSAY_RE,
        json={
            "assays": [
                {"assay_chembl_id": "CHEMBL_A1", "confidence_score": 9},
                {"assay_chembl_id": "CHEMBL_A2", "confidence_score": 4},
            ],
            "page_meta": {"next": None},
        },
    )
    # /target: only T1 survives confidence. T2 is registered as a guard but must NOT
    # be requested (A2 dropped it), so it must NOT appear in the result either.
    httpx_mock.add_response(
        url=_TARGET_RE,
        json={
            "targets": [
                {
                    "target_chembl_id": "CHEMBL_T1",
                    "target_type": "SINGLE PROTEIN",
                    "tax_id": 9606,
                    "organism": "Homo sapiens",
                    "target_components": [{"accession": "P04637"}],
                },
                {
                    "target_chembl_id": "CHEMBL_T2",
                    "target_type": "SINGLE PROTEIN",
                    "tax_id": 9606,
                    "organism": "Homo sapiens",
                    "target_components": [{"accession": "P99999"}],
                },
            ],
            "page_meta": {"next": None},
        },
    )

    async with httpx.AsyncClient() as c:
        hits = await ChemblClient(c).targets_for_inchikey("AAA", min_pchembl=5.0, min_confidence=7)

    accs = {h.uniprot_accession for h in hits}
    assert accs == {"P04637"}
    assert "P99999" not in accs
    assert hits[0].pchembl_value == 6.5
    assert hits[0].activity_type == "IC50"


@pytest.mark.asyncio
async def test_zero_qualifying_activities_returns_empty(httpx_mock):
    httpx_mock.add_response(
        url=_ACTIVITY_RE,
        json={"activities": [], "page_meta": {"next": None}},
    )
    async with httpx.AsyncClient() as c:
        hits = await ChemblClient(c).targets_for_inchikey("AAA", min_pchembl=5.0, min_confidence=7)
    assert hits == []


@pytest.mark.asyncio
async def test_outage_raises_service_unavailable(httpx_mock):
    # attempts=3 consumes exactly three 503s on the first /activity call.
    httpx_mock.add_response(url=_ACTIVITY_RE, status_code=503)
    httpx_mock.add_response(url=_ACTIVITY_RE, status_code=503)
    httpx_mock.add_response(url=_ACTIVITY_RE, status_code=503)
    async with httpx.AsyncClient() as c:
        with pytest.raises(ServiceUnavailableError):
            await ChemblClient(c).targets_for_inchikey("AAA", min_pchembl=5.0, min_confidence=7)
