"""Unit tests for integrations/uniprot.py (gene-symbol search path).

Exercises the REAL HTTP request built by ``_search_by_gene`` via pytest-httpx,
rather than mocking ``validate_human_target`` wholesale. This is the layer that
shipped a broken request: ``fields=...,organism`` — ``organism`` is not a valid
UniProt return field (valid names are ``organism_name`` / ``organism_id``), so
UniProt rejected every gene search with HTTP 400 and strict manual-target
validation was 100% broken.
"""
from __future__ import annotations

import pytest

from integrations.uniprot import validate_human_target

# Realistic shape of a UniProt /uniprotkb/search result for a human gene.
_AKT1_SEARCH_RESPONSE = {
    "results": [
        {
            "primaryAccession": "P31749",
            "genes": [{"geneName": {"value": "AKT1"}}],
            "proteinDescription": {
                "recommendedName": {
                    "fullName": {"value": "RAC-alpha serine/threonine-protein kinase"}
                }
            },
        }
    ]
}


@pytest.mark.asyncio
async def test_search_by_gene_does_not_request_invalid_organism_field(httpx_mock):
    """The outgoing UniProt search must not request the invalid ``organism`` field.

    Regression guard for the HTTP 400 bug: UniProt rejects ``organism`` as a
    return field. The request must request only fields that actually exist and
    that the parser consumes (accession, gene_names, protein_name).
    """
    httpx_mock.add_response(json=_AKT1_SEARCH_RESPONSE)

    await validate_human_target("AKT1", None)

    req = httpx_mock.get_requests()[0]
    fields = req.url.params.get("fields")
    assert fields is not None, "search request must send a 'fields' param"
    tokens = [t.strip() for t in fields.split(",")]

    assert "organism" not in tokens, (
        f"'organism' is not a valid UniProt return field (got fields={fields!r}); "
        "use 'organism_name'/'organism_id' or omit it — bare 'organism' causes HTTP 400."
    )
    # The parser depends on these three fields being present.
    assert "accession" in tokens
    assert "gene_names" in tokens
    assert "protein_name" in tokens


@pytest.mark.asyncio
async def test_search_by_gene_resolves_human_symbol(httpx_mock):
    """A known human gene symbol resolves to its accession, gene, and protein name."""
    httpx_mock.add_response(json=_AKT1_SEARCH_RESPONSE)

    result = await validate_human_target("akt1", None)

    assert result.gene_symbol == "AKT1"
    assert result.uniprot_accession == "P31749"
    assert result.protein_name == "RAC-alpha serine/threonine-protein kinase"


@pytest.mark.asyncio
async def test_search_by_gene_restricts_to_reviewed_swissprot(httpx_mock):
    """Gene search restricts to reviewed (Swiss-Prot) entries for the canonical accession.

    Without ``reviewed:true``, UniProt's relevance sort with size=1 can return an
    unreviewed TrEMBL fragment first (live: EGFR -> C9JYS6, TP53 -> S4R334 instead
    of canonical P00533 / P04637). The reviewed filter pins the canonical entry.
    """
    httpx_mock.add_response(json=_AKT1_SEARCH_RESPONSE)

    await validate_human_target("EGFR", None)

    req = httpx_mock.get_requests()[0]
    query = req.url.params.get("query")
    assert query is not None and "reviewed:true" in query, (
        f"search query must restrict to reviewed entries, got: {query!r}"
    )


@pytest.mark.asyncio
async def test_lookup_by_accession_malformed_gives_clear_message(httpx_mock):
    """A malformed accession (UniProt 400) surfaces a clear 'invalid format' message.

    UniProt returns 400 (not 404) for accession strings that violate its format,
    e.g. 'FOO'. The error must name the format problem rather than a generic
    'request failed', so the caller can map it to a useful validation error.
    """
    httpx_mock.add_response(
        status_code=400,
        json={"url": "...", "messages": ["The 'accession' value has invalid format."]},
    )

    with pytest.raises(ValueError, match="invalid format"):
        await validate_human_target(None, "FOO")


@pytest.mark.asyncio
async def test_lookup_by_accession_not_found_gives_clear_message(httpx_mock):
    """A well-formed but nonexistent accession (UniProt 404) says 'not found'."""
    httpx_mock.add_response(status_code=404, json={"messages": ["Resource not found"]})

    with pytest.raises(ValueError, match="not found"):
        await validate_human_target(None, "Q00000")
