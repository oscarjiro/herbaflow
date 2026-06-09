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
async def test_resolve_nonhuman_or_missing_returns_none(httpx_mock):
    httpx_mock.add_response(json={"results": []})
    async with httpx.AsyncClient() as c:
        rec = await UniProtClient(c).resolve("Q99999")
    assert rec is None


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
