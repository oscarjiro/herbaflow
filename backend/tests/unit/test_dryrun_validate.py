"""Dry-run ``POST /analyses/validate-inputs`` — resolves inputs, creates NO run.

The endpoint wraps the unified resolution service (``resolve_targets`` /
``resolve_compounds``) and returns its ``ResolveResult.to_payload()`` shape. It must
NOT create an analysis run.

Test #1 (targets) drives the REAL route through a ``TestClient`` with the
``get_session`` dependency overridden to a stub session — proving the wiring and the
"no run created" guarantee (``analysis_repo.create_run`` is asserted never called).
The provider (UniProt) is mocked offline. Tests #2/#4 call the handler function
directly (offline). Test #3 proves a DB cache hit yields ``reused > 0`` with no
provider round-trip.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import app.routers.analyses as analyses
import pytest
from app.database import get_session
from app.main import app
from app.schemas.analysis import ValidateInputsRequest, ValidateScopesRequest
from app.services.input_validation import LineFailure, ResolveResult
from fastapi.testclient import TestClient

PAYLOAD_KEYS = {"valid", "failed", "normalized", "duplicates", "reused", "enriched"}


class _ExecResult:
    """Mimics ``await session.exec(stmt)`` — exposes ``.first()``."""

    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _MissSession:
    """Async session stub: every DB-first lookup is a miss (returns None)."""

    async def exec(self, _stmt):
        return _ExecResult(None)

    def add(self, _obj):
        pass

    async def commit(self):
        pass


def _make_target_row(gene, accession, protein_name=None):
    t = MagicMock()
    t.gene_symbol = gene
    t.uniprot_accession = accession
    t.protein_name = protein_name
    return t


# ---------------------------------------------------------------------------
# Test 1 — real route: target kind returns the payload shape AND creates no run.
# ---------------------------------------------------------------------------
def test_validate_targets_route_returns_payload_and_creates_no_run():
    """POST /analyses/validate-inputs (kind=target) → 200 + full payload shape, and
    NO run is created (create_run is never called). Drives the real route via
    TestClient with get_session overridden to a stub session; resolve_targets is
    mocked so no UniProt call happens."""
    canned = ResolveResult(
        valid=[{"target_id": "uuid-tp53", "gene_symbol": "TP53", "uniprot_id": "P04637",
                "protein_name": "p53", "compound_ids": [], "sources": ["manual"]}],
        enriched=1,
    )

    async def _override_session():
        yield _MissSession()

    app.dependency_overrides[get_session] = _override_session
    try:
        with patch.object(analyses.analysis_repo, "create_run",
                          new=AsyncMock(side_effect=AssertionError("must not create a run"))) as create_run_mock, \
             patch("app.services.input_validation.resolve_targets",
                   new=AsyncMock(return_value=canned)):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/analyses/validate-inputs",
                json={"kind": "target", "inputs": ["TP53"]},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == PAYLOAD_KEYS
    assert body["enriched"] == 1
    assert len(body["valid"]) == 1
    # No run was created during a dry-run validation.
    create_run_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2 — compound kind returns the payload shape (handler called directly, offline).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_compounds_returns_payload_and_creates_no_run():
    """kind=compound → resolve_compounds payload shape; no create_run. PubChem is
    never hit because resolve_compounds is mocked with a canned result."""
    canned = ResolveResult(
        valid=[{"compound_id": "uuid-eth", "canonical_name": "Ethanol"}],
        failed=[LineFailure(line=2, input="BAD", reason="not found in PubChem")],
        enriched=1,
    )

    with patch.object(analyses.analysis_repo, "create_run",
                      new=AsyncMock(side_effect=AssertionError("must not create a run"))) as create_run_mock, \
         patch("app.services.input_validation.resolve_compounds",
               new=AsyncMock(return_value=canned)):
        body = ValidateInputsRequest(kind="compound", inputs=["CCO", "BAD"])
        out = await analyses.validate_inputs(None, body, session=_MissSession())

    assert set(out.keys()) == PAYLOAD_KEYS
    assert out["enriched"] == 1
    assert out["failed"][0]["input"] == "BAD"
    create_run_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3 — cached input → reused > 0 with NO provider call.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_targets_cache_hit_reused_no_provider_call():
    """A DB cache hit (stubbed session returns a prepared Target row) yields
    reused > 0 and the provider (UniProt validate_human_target) is NEVER called.

    Drives the REAL resolve_targets (not mocked) so the DB-first reuse path is
    exercised; only the UniProt round-trip is patched, and we assert it was not
    called."""
    cached_row = _make_target_row("TP53", "P04637", "Cellular tumor antigen p53")

    class _HitSession:
        async def exec(self, _stmt):
            return _ExecResult(cached_row)

        def add(self, _obj):
            pass

        async def commit(self):
            pass

    uniprot_mock = AsyncMock(side_effect=AssertionError("provider must not be called on cache hit"))
    with patch.object(analyses.analysis_repo, "create_run",
                      new=AsyncMock(side_effect=AssertionError("must not create a run"))), \
         patch("app.services.input_validation.validate_human_target", new=uniprot_mock), \
         patch("app.services.input_validation.persist_validated_targets", new=AsyncMock(return_value=0)):
        body = ValidateInputsRequest(kind="target", inputs=["TP53"])
        out = await analyses.validate_inputs(None, body, session=_HitSession())

    assert out["reused"] > 0
    assert out["enriched"] == 0
    uniprot_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4 — unknown kind → 422.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_unknown_kind_returns_422():
    """An unrecognized kind raises HTTPException(422) and never touches a provider
    or creates a run."""
    from fastapi import HTTPException

    with patch.object(analyses.analysis_repo, "create_run",
                      new=AsyncMock(side_effect=AssertionError("must not create a run"))), \
         patch("app.services.input_validation.resolve_targets",
               new=AsyncMock(side_effect=AssertionError("provider must not be called"))), \
         patch("app.services.input_validation.resolve_compounds",
               new=AsyncMock(side_effect=AssertionError("provider must not be called"))):
        body = ValidateInputsRequest(kind="bogus", inputs=["X"])
        with pytest.raises(HTTPException) as ei:
            await analyses.validate_inputs(None, body, session=_MissSession())

    assert ei.value.status_code == 422


# ===========================================================================
# POST /analyses/validate-input-scopes — multi-scope dry-run (shared union)
# ===========================================================================
@pytest.mark.asyncio
async def test_validate_scopes_returns_per_scope_payloads_no_run():
    """Both target scopes come back keyed by scope name, in payload shape, no run."""
    canned = {
        "targets": ResolveResult(valid=[{"gene_symbol": "AKT1"}], enriched=1),
        "disease_targets": ResolveResult(valid=[{"gene_symbol": "TP53"}], reused=1),
    }
    with patch.object(analyses.analysis_repo, "create_run",
                      new=AsyncMock(side_effect=AssertionError("must not create a run"))) as create_run_mock, \
         patch("app.services.input_validation.resolve_target_scopes",
               new=AsyncMock(return_value=canned)):
        body = ValidateScopesRequest.model_validate({"scopes": [
            {"scope": "targets", "inputs": ["AKT1"]},
            {"scope": "disease_targets", "inputs": ["TP53"], "lenient": True},
        ]})
        out = await analyses.validate_input_scopes(None, body, session=_MissSession())

    assert set(out["results"]) == {"targets", "disease_targets"}
    assert set(out["results"]["targets"]) == PAYLOAD_KEYS
    assert out["results"]["targets"]["valid"][0]["gene_symbol"] == "AKT1"
    assert out["results"]["disease_targets"]["reused"] == 1
    create_run_mock.assert_not_called()


@pytest.mark.asyncio
async def test_validate_scopes_unknown_scope_returns_422():
    """An unrecognized scope name raises HTTPException(422) before any resolution."""
    from fastapi import HTTPException

    with patch("app.services.input_validation.resolve_target_scopes",
               new=AsyncMock(side_effect=AssertionError("must not resolve"))):
        body = ValidateScopesRequest.model_validate(
            {"scopes": [{"scope": "bogus", "inputs": ["X"]}]}
        )
        with pytest.raises(HTTPException) as ei:
            await analyses.validate_input_scopes(None, body, session=_MissSession())

    assert ei.value.status_code == 422
