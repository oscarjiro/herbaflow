"""Unit tests for the unified DB-first resolution service (resolve_targets).

Covers the 6 required behaviors:
1. DB cache hit by accession -> reused, NO UniProt request made.
2. DB cache hit by offline-normalized symbol -> reused, NO UniProt request made.
3. Novel symbol (DB miss) -> UniProt called once, enriched, persisted.
4. Lenient + unrecognized symbol (UniProt ValueError) -> kept flagged, never failed.
5. Within-batch dup + a key already in existing_keys -> duplicates populated.
6. Strict not-found/invalid -> failed[].line is the correct 1-based index.

The async session is stubbed with a tiny fake whose ``exec`` returns prepared
``Target`` rows (or None) so DB-first lookups are testable without a live DB.
UniProt is exercised/observed through pytest-httpx (``httpx_mock``) — the cache-hit
tests assert that NO HTTP request was made.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.models.target import Target
from app.services import gene_symbols
from app.services.input_validation import LineFailure, ResolveResult, resolve_targets

# Realistic UniProt /uniprotkb/search result for a human gene symbol.
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


class _Result:
    """Mimics the object returned by ``await session.exec(stmt)`` — has ``.first()``."""

    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    """Async session stub.

    ``rows`` is an ordered list of ``Target | None`` returned by successive
    ``exec`` calls, mirroring one SELECT per DB-first lookup. ``add``/``commit``
    are recorded so persistence is observable.
    """

    def __init__(self, rows):
        self._rows = list(rows)
        self.added = []
        self.commits = 0

    async def exec(self, _stmt):
        row = self._rows.pop(0) if self._rows else None
        return _Result(row)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def _target(gene, acc, protein="prot"):
    return Target(
        target_id=f"uuid-{acc or gene}",
        canonical_key=f"uniprot:{acc}" if acc else f"gene:{gene}",
        gene_symbol=gene,
        uniprot_accession=acc,
        protein_name=protein,
    )


@pytest.fixture(autouse=True)
def _hgnc_map():
    """Deterministic offline HGNC map for the duration of each test."""
    gene_symbols._MAP = {
        "AKT1": {"symbol": "AKT1", "kind": "approved"},
        "TP53": {"symbol": "TP53", "kind": "approved"},
        "EGFR": {"symbol": "EGFR", "kind": "approved"},
        "TNFA": {"symbol": "TNF", "kind": "alias"},
        "TNF": {"symbol": "TNF", "kind": "approved"},
    }
    yield
    gene_symbols._MAP = None


# ---------------------------------------------------------------------------
# Test 1: accession cache hit -> reused, NO UniProt call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_accession_cache_hit_no_uniprot(httpx_mock):
    session = _FakeSession(rows=[_target("TP53", "P04637", "Cellular tumor antigen p53")])

    result = await resolve_targets(
        ["P04637"], lenient=False, existing_keys=set(), session=session
    )

    assert result.reused == 1
    assert result.enriched == 0
    assert len(result.valid) == 1
    assert result.valid[0]["uniprot_id"] == "P04637"
    assert result.valid[0]["gene_symbol"] == "TP53"
    assert result.valid[0]["sources"] == ["cache"]
    # The cache hit must short-circuit BEFORE any provider round-trip.
    assert httpx_mock.get_requests() == []


# ---------------------------------------------------------------------------
# Test 2: symbol normalizes offline AND is cached by symbol -> reused, NO UniProt
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_symbol_cache_hit_after_normalize_no_uniprot(httpx_mock):
    # "TNFA" normalizes offline to "TNF"; the cached row is keyed by gene_symbol TNF.
    session = _FakeSession(rows=[_target("TNF", "P01375", "Tumor necrosis factor")])

    result = await resolve_targets(
        ["TNFA"], lenient=False, existing_keys=set(), session=session
    )

    assert result.reused == 1
    assert result.enriched == 0
    assert result.valid[0]["gene_symbol"] == "TNF"
    assert result.valid[0]["sources"] == ["cache"]
    # Offline normalization recorded.
    assert {"from": "TNFA", "to": "TNF"} in result.normalized
    assert httpx_mock.get_requests() == []


# ---------------------------------------------------------------------------
# Test 3: novel symbol (DB miss) -> UniProt called once, enriched, persisted
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_novel_symbol_enriches_and_persists(httpx_mock):
    httpx_mock.add_response(json=_AKT1_SEARCH_RESPONSE)
    session = _FakeSession(rows=[None])  # DB miss

    with patch(
        "app.services.input_validation.persist_validated_targets",
        new=AsyncMock(return_value=1),
    ) as mock_persist:
        result = await resolve_targets(
            ["AKT1"], lenient=False, existing_keys=set(), session=session
        )

    # Exactly one provider round-trip.
    assert len(httpx_mock.get_requests()) == 1
    assert result.enriched == 1
    assert result.reused == 0
    assert len(result.valid) == 1
    assert result.valid[0]["uniprot_id"] == "P31749"
    assert result.valid[0]["protein_name"] == "RAC-alpha serine/threonine-protein kinase"
    assert result.valid[0]["sources"] == ["manual"]
    # The enriched dict was handed to the persist service.
    mock_persist.assert_awaited_once()
    persisted_arg = mock_persist.await_args.args[0]
    assert persisted_arg[0]["uniprot_id"] == "P31749"


# ---------------------------------------------------------------------------
# Test 4: lenient + unrecognized symbol -> kept flagged, never failed/dropped
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lenient_unrecognized_symbol_kept_flagged(httpx_mock):
    # "ZZZ9" is absent from the HGNC map (-> canonical "ZZZ9", unrecognized) and
    # UniProt returns 404 for the gene search -> ValueError. Lenient keeps it.
    httpx_mock.add_response(status_code=400, json={"messages": ["bad"]})
    session = _FakeSession(rows=[None])  # DB miss

    with patch(
        "app.services.input_validation.persist_validated_targets",
        new=AsyncMock(return_value=0),
    ):
        result = await resolve_targets(
            ["ZZZ9"], lenient=True, existing_keys=set(), session=session
        )

    assert result.failed == []
    assert len(result.valid) == 1
    kept = result.valid[0]
    assert kept["sources"] == ["manual_unrecognized"]
    assert kept["uniprot_id"] is None
    assert kept["target_id"] == "manual:ZZZ9"


# ---------------------------------------------------------------------------
# Test 5: within-batch dup + a key already in existing_keys -> duplicates
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_within_batch_and_existing_dedup(httpx_mock):
    httpx_mock.add_response(json=_AKT1_SEARCH_RESPONSE)
    # First AKT1 -> DB miss -> enrich. Second AKT1 -> dup (no exec). P04637 -> in
    # existing_keys so it dedups before any exec.
    session = _FakeSession(rows=[None])

    with patch(
        "app.services.input_validation.persist_validated_targets",
        new=AsyncMock(return_value=1),
    ):
        result = await resolve_targets(
            ["AKT1", "AKT1", "P04637"],
            lenient=False,
            existing_keys={"P04637"},
            session=session,
        )

    # Only the first AKT1 is valid; the second AKT1 and the pre-existing P04637 drop.
    assert result.enriched == 1
    assert len(result.valid) == 1
    assert "AKT1" in result.duplicates
    assert "P04637" in result.duplicates
    assert len(result.duplicates) == 2
    # Only one provider call (the first AKT1).
    assert len(httpx_mock.get_requests()) == 1


# ---------------------------------------------------------------------------
# Test 6: strict not-found -> failed[].line is the correct 1-based index
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_strict_failure_reports_correct_line(httpx_mock):
    # Two inputs: a valid symbol (line 1) then an unrecognized one (line 2).
    httpx_mock.add_response(json=_AKT1_SEARCH_RESPONSE)  # AKT1 success
    httpx_mock.add_response(status_code=400, json={"messages": ["bad"]})  # FAKEGENE 400
    session = _FakeSession(rows=[None, None])  # both DB misses

    with patch(
        "app.services.input_validation.persist_validated_targets",
        new=AsyncMock(return_value=1),
    ):
        result = await resolve_targets(
            ["AKT1", "FAKEGENE"],
            lenient=False,
            existing_keys=set(),
            session=session,
        )

    assert len(result.valid) == 1
    assert len(result.failed) == 1
    fail = result.failed[0]
    assert fail.line == 2  # 1-based index of FAKEGENE
    assert fail.input == "FAKEGENE"
    assert "UniProt" in fail.reason or "human protein" in fail.reason


# ---------------------------------------------------------------------------
# Bonus: empty line is reported as a failure at its 1-based index, no provider call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_line_failure(httpx_mock):
    session = _FakeSession(rows=[])

    result = await resolve_targets(
        ["   "], lenient=False, existing_keys=set(), session=session
    )

    assert result.failed[0].line == 1
    assert result.failed[0].reason == "empty line"
    assert httpx_mock.get_requests() == []


def test_resolve_result_to_payload_shape():
    """to_payload serializes failures via __dict__ and exposes all keys."""
    rr = ResolveResult(
        valid=[{"target_id": "x"}],
        failed=[],
        normalized=[{"from": "A", "to": "B"}],
        duplicates=["dup"],
        reused=2,
        enriched=3,
    )
    rr.failed.append(LineFailure(line=1, input="z", reason="r"))
    payload = rr.to_payload()
    assert set(payload) == {"valid", "failed", "normalized", "duplicates", "reused", "enriched"}
    assert payload["failed"][0] == {"line": 1, "input": "z", "reason": "r"}
    assert payload["reused"] == 2
    assert payload["enriched"] == 3
