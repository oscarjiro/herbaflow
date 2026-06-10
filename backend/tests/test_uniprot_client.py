"""UniProt client — human (9606) accession + gene-symbol resolution."""

from __future__ import annotations

import httpx
import pytest

from app.integrations.uniprot import UniProtClient

_HIT = {
    "results": [
        {
            "primaryAccession": "P04637",
            "genes": [{"geneName": {"value": "TP53"}}],
            "proteinDescription": {
                "recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}}
            },
        }
    ]
}


@pytest.mark.asyncio
async def test_resolve_accession_human_hit(httpx_mock):
    httpx_mock.add_response(json=_HIT)
    async with httpx.AsyncClient() as c:
        rec = await UniProtClient(c).resolve("P04637")
    assert rec is not None
    assert rec.uniprot_accession == "P04637"
    assert rec.gene_symbol == "TP53"
    assert rec.protein_name == "Cellular tumor antigen p53"
    # The client must filter on the human organism via organism_id (not the bare `organism` field).
    sent = str(httpx_mock.get_requests()[0].url)
    assert "organism_id%3A9606" in sent or "organism_id:9606" in sent
    assert "accession%3AP04637" in sent or "accession:P04637" in sent


@pytest.mark.asyncio
async def test_resolve_queries_secondary_accession_field(httpx_mock):
    # A secondary (merged/retired) accession must still resolve to its entry, whose
    # primaryAccession is returned — so identity converges on the primary. The query
    # searches `sec_acc:` (secondary) in addition to `accession:` (primary).
    # See https://www.uniprot.org/help/query-fields.
    httpx_mock.add_response(json=_HIT)
    async with httpx.AsyncClient() as c:
        rec = await UniProtClient(c).resolve("Q14225")
    assert rec is not None
    assert rec.uniprot_accession == "P04637"  # the primary, not the queried secondary
    sent = str(httpx_mock.get_requests()[0].url)
    assert "sec_acc%3AQ14225" in sent or "sec_acc:Q14225" in sent


@pytest.mark.asyncio
async def test_resolve_nonhuman_or_missing_returns_none(httpx_mock):
    httpx_mock.add_response(json={"results": []})
    async with httpx.AsyncClient() as c:
        rec = await UniProtClient(c).resolve("Q99999")
    assert rec is None


@pytest.mark.asyncio
async def test_resolve_malformed_accession_400_returns_none(httpx_mock):
    # A non-UniProt accession (e.g. a ChEMBL target carrying a GenBank id) makes UniProt
    # 400; the client skips it (None) instead of crashing the run.
    httpx_mock.add_response(status_code=400)
    async with httpx.AsyncClient() as c:
        rec = await UniProtClient(c).resolve("AAI32679")
    assert rec is None


@pytest.mark.asyncio
async def test_resolve_retries_transient_5xx_then_succeeds(httpx_mock):
    # raise_for_status is INSIDE _call, so a transient 503 is retried rather than propagated.
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(json=_HIT)
    async with httpx.AsyncClient() as c:
        rec = await UniProtClient(c).resolve("P04637")
    assert rec is not None
    assert rec.uniprot_accession == "P04637"


@pytest.mark.asyncio
async def test_resolve_symbol_human_hit(httpx_mock):
    httpx_mock.add_response(json=_HIT)
    async with httpx.AsyncClient() as c:
        rec = await UniProtClient(c).resolve_symbol("TP53")
    assert rec is not None
    assert rec.uniprot_accession == "P04637"
    assert rec.gene_symbol == "TP53"
    sent = str(httpx_mock.get_requests()[0].url)
    assert "organism_id%3A9606" in sent or "organism_id:9606" in sent
    assert "gene_exact%3ATP53" in sent or "gene_exact:TP53" in sent
