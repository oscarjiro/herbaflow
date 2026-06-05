"""Unit tests for resolve_target_scopes — the shared-union multi-scope resolver.

Verifies that a target appearing in more than one scope is resolved (DB-first +
UniProt) EXACTLY ONCE, fanned back out to every requesting scope, with the
lenient keep/drop decision applied per-scope. The async session is stubbed with
the same tiny fake used by test_input_validation; UniProt is observed via
pytest-httpx.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.models.target import Target
from app.services import gene_symbols
from app.services.input_validation import ScopeRequest, resolve_target_scopes

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
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    """``rows`` is returned by successive ``exec`` calls (one per DB-first lookup)."""

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
    gene_symbols._MAP = {
        "AKT1": {"symbol": "AKT1", "kind": "approved"},
        "TP53": {"symbol": "TP53", "kind": "approved"},
        "EGFR": {"symbol": "EGFR", "kind": "approved"},
    }
    yield
    gene_symbols._MAP = None


@pytest.mark.asyncio
async def test_shared_target_resolved_once_appears_in_both(httpx_mock):
    """AKT1 in both scopes → ONE UniProt call, present in BOTH scopes' valid, persisted once."""
    httpx_mock.add_response(json=_AKT1_SEARCH_RESPONSE)
    session = _FakeSession(rows=[None])  # the union has a single key → one DB lookup (miss)

    with patch(
        "app.services.input_validation.persist_validated_targets",
        new=AsyncMock(return_value=1),
    ) as mock_persist:
        results = await resolve_target_scopes(
            [
                ScopeRequest("targets", ["AKT1"], lenient=False),
                ScopeRequest("disease_targets", ["AKT1"], lenient=False),
            ],
            session=session,
        )

    assert len(httpx_mock.get_requests()) == 1  # resolved once for both scopes
    assert results["targets"].valid[0]["uniprot_id"] == "P31749"
    assert results["disease_targets"].valid[0]["uniprot_id"] == "P31749"
    assert results["targets"].enriched == 1
    assert results["disease_targets"].enriched == 1
    # One unique enriched target persisted once.
    mock_persist.assert_awaited_once()
    assert len(mock_persist.await_args.args[0]) == 1


@pytest.mark.asyncio
async def test_shared_db_hit_reused_in_both_no_uniprot(httpx_mock):
    """A cached shared target → reused in both scopes, zero provider calls."""
    session = _FakeSession(rows=[_target("AKT1", "P31749")])  # one lookup, hit

    with patch(
        "app.services.input_validation.persist_validated_targets",
        new=AsyncMock(return_value=0),
    ):
        results = await resolve_target_scopes(
            [
                ScopeRequest("targets", ["AKT1"], lenient=False),
                ScopeRequest("disease_targets", ["AKT1"], lenient=False),
            ],
            session=session,
        )

    assert httpx_mock.get_requests() == []
    assert results["targets"].reused == 1
    assert results["disease_targets"].reused == 1
    assert results["targets"].valid[0]["gene_symbol"] == "AKT1"


@pytest.mark.asyncio
async def test_per_scope_lenient_keep_vs_drop(httpx_mock):
    """A shared UNKNOWN symbol resolves once; strict scope drops it, lenient scope keeps it."""
    httpx_mock.add_response(status_code=400, json={"messages": ["bad"]})
    session = _FakeSession(rows=[None])  # union {ZZZ9}, one lookup (miss)

    with patch(
        "app.services.input_validation.persist_validated_targets",
        new=AsyncMock(return_value=0),
    ):
        results = await resolve_target_scopes(
            [
                ScopeRequest("targets", ["ZZZ9"], lenient=False),
                ScopeRequest("disease_targets", ["ZZZ9"], lenient=True),
            ],
            session=session,
        )

    assert len(httpx_mock.get_requests()) == 1  # resolved once despite two scopes
    # Strict scope drops it.
    assert results["targets"].valid == []
    assert results["targets"].failed[0].input == "ZZZ9"
    # Lenient scope keeps it flagged.
    assert results["disease_targets"].failed == []
    assert len(results["disease_targets"].valid) == 1
    assert results["disease_targets"].valid[0]["sources"] == ["manual_unrecognized"]


@pytest.mark.asyncio
async def test_in_scope_dedup_and_failure_line_numbers(httpx_mock):
    """Within a scope, duplicates collapse and failures report the correct 1-based line."""
    httpx_mock.add_response(json=_AKT1_SEARCH_RESPONSE)              # AKT1 success
    httpx_mock.add_response(status_code=400, json={"messages": ["bad"]})  # FAKEGENE fail
    session = _FakeSession(rows=[None, None])  # union {AKT1, FAKEGENE}, two lookups (both miss)

    with patch(
        "app.services.input_validation.persist_validated_targets",
        new=AsyncMock(return_value=1),
    ):
        results = await resolve_target_scopes(
            [ScopeRequest("targets", ["AKT1", "AKT1", "FAKEGENE"], lenient=False)],
            session=session,
        )

    r = results["targets"]
    assert "AKT1" in r.duplicates
    assert len(r.valid) == 1
    assert r.failed[0].line == 3          # FAKEGENE is the 3rd input line
    assert r.failed[0].input == "FAKEGENE"
    assert len(httpx_mock.get_requests()) == 2  # AKT1 + FAKEGENE, the dup adds nothing


@pytest.mark.asyncio
async def test_distinct_targets_resolve_independently(httpx_mock):
    """Non-overlapping scopes each resolve their own targets (no false sharing)."""
    httpx_mock.add_response(json=_AKT1_SEARCH_RESPONSE)  # AKT1
    httpx_mock.add_response(  # TP53
        json={
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
    )
    session = _FakeSession(rows=[None, None])  # union {AKT1, TP53}, two lookups

    with patch(
        "app.services.input_validation.persist_validated_targets",
        new=AsyncMock(return_value=2),
    ) as mock_persist:
        results = await resolve_target_scopes(
            [
                ScopeRequest("targets", ["AKT1"], lenient=False),
                ScopeRequest("disease_targets", ["TP53"], lenient=False),
            ],
            session=session,
        )

    assert len(httpx_mock.get_requests()) == 2
    assert results["targets"].valid[0]["gene_symbol"] == "AKT1"
    assert results["disease_targets"].valid[0]["gene_symbol"] == "TP53"
    # Two distinct enriched targets, persisted once together.
    assert len(mock_persist.await_args.args[0]) == 2
