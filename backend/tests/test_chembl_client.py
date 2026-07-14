import re

import httpx
import pytest

from app.errors import ServiceUnavailableError
from app.integrations.chembl import ChemblClient

_MOLECULE_RE = re.compile(r".*/data/molecule.*")
_ACTIVITY_RE = re.compile(r".*/data/activity.*")
_ASSAY_RE = re.compile(r".*/data/assay.*")
_TARGET_RE = re.compile(r".*/data/target.*")

# The InChIKey is resolved to a molecule id first (the /activity InChIKey filter is a no-op
# on the real API), so every join test seeds a /molecule response.
_MOLECULE_HIT = {"molecules": [{"molecule_chembl_id": "CHEMBL_M1"}], "page_meta": {"next": None}}


@pytest.mark.asyncio
async def test_join_filters_by_pchembl_confidence_human_and_type(httpx_mock):
    # /molecule: resolve the InChIKey to a molecule id (the load-bearing first step).
    httpx_mock.add_response(url=_MOLECULE_RE, json=_MOLECULE_HIT)
    # /activity (by molecule id): one fully-qualifying, one below pchembl, one non-human, one
    # whose assay confidence is too low. accession/confidence are NOT on these rows.
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
async def test_resolves_inchikey_via_molecule_endpoint(httpx_mock):
    # The /activity request must be keyed on the resolved molecule id, NOT the InChIKey
    # (the InChIKey filter is silently ignored on /activity by the real API).
    httpx_mock.add_response(url=_MOLECULE_RE, json=_MOLECULE_HIT)
    httpx_mock.add_response(url=_ACTIVITY_RE, json={"activities": [], "page_meta": {"next": None}})
    async with httpx.AsyncClient() as c:
        await ChemblClient(c).targets_for_inchikey("AAA", min_pchembl=5.0, min_confidence=7)

    reqs = httpx_mock.get_requests()
    mol_req = next(r for r in reqs if "/data/molecule" in str(r.url))
    act_req = next(r for r in reqs if "/data/activity" in str(r.url))
    assert "standard_inchi_key=AAA" in str(mol_req.url)
    assert "molecule_chembl_id__in=CHEMBL_M1" in str(act_req.url)
    assert "AAA" not in str(act_req.url)  # the InChIKey never reaches /activity


@pytest.mark.asyncio
async def test_not_in_chembl_returns_empty(httpx_mock):
    # No molecule for the InChIKey -> the compound is absent from ChEMBL -> [] (no /activity).
    httpx_mock.add_response(url=_MOLECULE_RE, json={"molecules": [], "page_meta": {"next": None}})
    async with httpx.AsyncClient() as c:
        hits = await ChemblClient(c).targets_for_inchikey("AAA", min_pchembl=5.0, min_confidence=7)
    assert hits == []
    assert all("/data/activity" not in str(r.url) for r in httpx_mock.get_requests())


@pytest.mark.asyncio
async def test_zero_qualifying_activities_returns_empty(httpx_mock):
    httpx_mock.add_response(url=_MOLECULE_RE, json=_MOLECULE_HIT)
    httpx_mock.add_response(
        url=_ACTIVITY_RE,
        json={"activities": [], "page_meta": {"next": None}},
    )
    async with httpx.AsyncClient() as c:
        hits = await ChemblClient(c).targets_for_inchikey("AAA", min_pchembl=5.0, min_confidence=7)
    assert hits == []


@pytest.mark.asyncio
async def test_connectivity_fallback_recovers_on_exact_miss(httpx_mock):
    # Exact standard-key lookup misses (our stored tautomer differs from ChEMBL's, e.g. curcumin
    # enol vs keto)... the connectivity (startswith skeleton) lookup then recovers the molecule.
    httpx_mock.add_response(url=_MOLECULE_RE, json={"molecules": [], "page_meta": {"next": None}})
    httpx_mock.add_response(url=_MOLECULE_RE, json=_MOLECULE_HIT)
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
                }
            ],
            "page_meta": {"next": None},
        },
    )
    httpx_mock.add_response(
        url=_ASSAY_RE,
        json={
            "assays": [{"assay_chembl_id": "CHEMBL_A1", "confidence_score": 9}],
            "page_meta": {"next": None},
        },
    )
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
                }
            ],
            "page_meta": {"next": None},
        },
    )

    async with httpx.AsyncClient() as c:
        hits = await ChemblClient(c).targets_for_inchikey(
            "ZIUSSTSXXLLKKK-KOBPDPAPSA-N",
            min_pchembl=5.0,
            min_confidence=7,
            connectivity_key="VFLDPWHFBUODDF",
        )

    assert {h.uniprot_accession for h in hits} == {"P04637"}
    mol_urls = [str(r.url) for r in httpx_mock.get_requests() if "/data/molecule" in str(r.url)]
    # Exact query fired first (full key), then the connectivity startswith fallback.
    assert any("standard_inchi_key=ZIUSSTSXXLLKKK" in u for u in mol_urls)
    assert any("standard_inchi_key__startswith=VFLDPWHFBUODDF" in u for u in mol_urls)


@pytest.mark.asyncio
async def test_no_connectivity_fallback_when_exact_hits(httpx_mock):
    # An exact molecule hit must NOT trigger the connectivity fallback (a precise match is
    # never widened to the whole skeleton).
    httpx_mock.add_response(url=_MOLECULE_RE, json=_MOLECULE_HIT)
    httpx_mock.add_response(url=_ACTIVITY_RE, json={"activities": [], "page_meta": {"next": None}})
    async with httpx.AsyncClient() as c:
        await ChemblClient(c).targets_for_inchikey(
            "AAA", min_pchembl=5.0, min_confidence=7, connectivity_key="SKELETON1234AB"
        )
    mol_urls = [str(r.url) for r in httpx_mock.get_requests() if "/data/molecule" in str(r.url)]
    assert len(mol_urls) == 1
    assert "startswith" not in mol_urls[0]


@pytest.mark.asyncio
async def test_connectivity_fallback_caps_molecule_ids(httpx_mock):
    # A common skeleton can match many ChEMBL molecules; the fallback is capped so the
    # downstream activity query never balloons.
    from urllib.parse import parse_qs, urlparse

    from app.integrations.chembl import _CONNECTIVITY_ID_CAP

    httpx_mock.add_response(url=_MOLECULE_RE, json={"molecules": [], "page_meta": {"next": None}})
    httpx_mock.add_response(
        url=_MOLECULE_RE,
        json={
            "molecules": [
                {"molecule_chembl_id": f"CHEMBL_M{i}"} for i in range(_CONNECTIVITY_ID_CAP + 10)
            ],
            "page_meta": {"next": None},
        },
    )
    httpx_mock.add_response(url=_ACTIVITY_RE, json={"activities": [], "page_meta": {"next": None}})

    async with httpx.AsyncClient() as c:
        await ChemblClient(c).targets_for_inchikey(
            "AAA", min_pchembl=5.0, min_confidence=7, connectivity_key="SKEL1234567890"
        )

    act_req = next(r for r in httpx_mock.get_requests() if "/data/activity" in str(r.url))
    ids = parse_qs(urlparse(str(act_req.url)).query)["molecule_chembl_id__in"][0].split(",")
    assert len(ids) == _CONNECTIVITY_ID_CAP


@pytest.mark.asyncio
async def test_outage_raises_service_unavailable(httpx_mock):
    # attempts=3 consumes exactly three 503s on the first (/molecule) call.
    httpx_mock.add_response(url=_MOLECULE_RE, status_code=503)
    httpx_mock.add_response(url=_MOLECULE_RE, status_code=503)
    httpx_mock.add_response(url=_MOLECULE_RE, status_code=503)
    async with httpx.AsyncClient() as c:
        with pytest.raises(ServiceUnavailableError):
            await ChemblClient(c).targets_for_inchikey("AAA", min_pchembl=5.0, min_confidence=7)
