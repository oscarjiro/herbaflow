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

import httpx
import pytest
from app.models.compound import Compound
from app.models.target import Target
from app.services import gene_symbols
from app.services.canonicalize import make_compound_id
from app.services.input_validation import (
    LineFailure,
    ResolveResult,
    resolve_compounds,
    resolve_targets,
)

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


# ===========================================================================
# resolve_compounds — DB-first compound resolution
# ===========================================================================

# A real aspirin InChIKey (14-10-1) so the regex classifier matches it.
_ASPIRIN_INCHIKEY = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"


def _compound(
    *,
    inchi_key: str | None = None,
    pubchem_cid: str | None = None,
    canonical_name: str = "compound",
    molecular_weight: float | None = 180.16,
    logp: float | None = 1.2,
) -> Compound:
    """Build a cached ``Compound`` row for cache-hit tests."""
    cid = make_compound_id(inchi_key) if inchi_key else "00000000-0000-0000-0000-000000000000"
    return Compound(
        compound_id=cid,
        canonical_key=f"inchikey:{(inchi_key or '').upper()}",
        canonical_name=canonical_name,
        inchi_key=inchi_key,
        pubchem_cid=pubchem_cid,
        molecular_weight=molecular_weight,
        logp=logp,
        hbond_donors=1,
        hbond_acceptors=4,
        rotatable_bonds=3,
        tpsa=63.6,
    )


def _validated_dict(*, inchikey: str, cid: str = "2244", compound_id: str | None = None) -> dict:
    """A canned ``validate_compound`` return value (the stage_1 compound shape)."""
    return {
        "compound_id": compound_id or make_compound_id(inchikey),
        "canonical_key": f"inchikey:{inchikey.upper()}",
        "pubchem_cid": cid,
        "inchikey": inchikey,
        "iupac_name": "2-acetyloxybenzoic acid",
        "molecular_formula": "C9H8O4",
        "molecular_weight": 180.16,
        "canonical_name": "2-acetyloxybenzoic acid",
        "plant_ids": [],
        "adme_pass": True,
        "is_np_exception": False,
        "is_pains_positive": False,
        "logp": 1.2,
        "tpsa": 63.6,
        "hbond_donors": 1,
        "hbond_acceptors": 4,
        "np_likeness_score": None,
        "rotatable_bonds": 3,
        "mw": 180.16,
        "xlogp": 1.2,
        "hbd": 1,
        "hba": 4,
        "lipinski_pass": True,
    }


def _client() -> httpx.AsyncClient:
    """A real client instance — never used when validate_compound is patched."""
    return httpx.AsyncClient()


# ---------------------------------------------------------------------------
# Test 1: InChIKey already cached -> reused, validate_compound NOT called
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_inchikey_cache_hit_no_pubchem():
    session = _FakeSession(rows=[_compound(inchi_key=_ASPIRIN_INCHIKEY, pubchem_cid="2244")])

    with patch(
        "app.services.input_validation.validate_compound",
        new=AsyncMock(return_value=None),
    ) as mock_validate, patch(
        "app.services.input_validation.persist_validated_compounds",
        new=AsyncMock(return_value=0),
    ):
        result = await resolve_compounds(
            [_ASPIRIN_INCHIKEY],
            existing_keys=set(),
            session=session,
            client=_client(),
        )

    assert result.reused == 1
    assert result.enriched == 0
    assert len(result.valid) == 1
    assert result.valid[0]["inchikey"] == _ASPIRIN_INCHIKEY
    assert result.valid[0]["pubchem_cid"] == "2244"
    assert result.valid[0]["sources"] == ["cache"]
    # The cache hit must short-circuit BEFORE any PubChem round-trip.
    mock_validate.assert_not_awaited()
    assert mock_validate.await_count == 0


# ---------------------------------------------------------------------------
# Test 2: CID input cached -> reused, validate_compound NOT called
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cid_cache_hit_no_pubchem():
    session = _FakeSession(
        rows=[_compound(inchi_key=_ASPIRIN_INCHIKEY, pubchem_cid="2244", canonical_name="aspirin")]
    )

    with patch(
        "app.services.input_validation.validate_compound",
        new=AsyncMock(return_value=None),
    ) as mock_validate, patch(
        "app.services.input_validation.persist_validated_compounds",
        new=AsyncMock(return_value=0),
    ):
        result = await resolve_compounds(
            ["2244"],
            existing_keys=set(),
            session=session,
            client=_client(),
        )

    assert result.reused == 1
    assert result.enriched == 0
    assert len(result.valid) == 1
    assert result.valid[0]["pubchem_cid"] == "2244"
    assert result.valid[0]["canonical_name"] == "aspirin"
    assert result.valid[0]["sources"] == ["cache"]
    mock_validate.assert_not_awaited()
    assert mock_validate.await_count == 0


# ---------------------------------------------------------------------------
# Test 3: novel SMILES (DB miss) -> validate_compound called EXACTLY ONCE,
#         enriched, valid[0] is the resolved dict, persist received it.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_novel_smiles_enriches_once_and_persists():
    canned = _validated_dict(inchikey=_ASPIRIN_INCHIKEY)
    # SMILES branch: one DB miss for the structure-resolved compound_id lookup.
    session = _FakeSession(rows=[None])

    with patch(
        "app.services.input_validation.validate_compound",
        new=AsyncMock(return_value=canned),
    ) as mock_validate, patch(
        "app.services.input_validation.persist_validated_compounds",
        new=AsyncMock(return_value=1),
    ) as mock_persist:
        result = await resolve_compounds(
            ["CC(=O)Oc1ccccc1C(=O)O"],
            existing_keys=set(),
            session=session,
            client=_client(),
        )

    # Proves NO double PubChem call — exactly one validate_compound round-trip.
    assert mock_validate.await_count == 1
    assert result.enriched == 1
    assert result.reused == 0
    assert len(result.valid) == 1
    assert result.valid[0]["compound_id"] == canned["compound_id"]
    assert result.valid[0]["inchikey"] == _ASPIRIN_INCHIKEY
    # The single resolved dict was handed to persist.
    mock_persist.assert_awaited_once()
    persisted_arg = mock_persist.await_args.args[0]
    assert len(persisted_arg) == 1
    assert persisted_arg[0]["compound_id"] == canned["compound_id"]
    assert persisted_arg[0]["pubchem_cid"] == "2244"


# ---------------------------------------------------------------------------
# Test 4: within-batch dup + existing_keys member -> duplicates, not double-valid
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_within_batch_and_existing_dedup_compounds():
    canned = _validated_dict(inchikey=_ASPIRIN_INCHIKEY)
    resolved_id = canned["compound_id"]
    # Pre-seed an existing compound_id (a different compound already selected).
    existing_id = make_compound_id("AAAAAAAAAAAAAA-BBBBBBBBBB-C")
    cached_existing = _compound(inchi_key="AAAAAAAAAAAAAA-BBBBBBBBBB-C", pubchem_cid="999")
    # First SMILES -> DB miss for resolved id (enrich). Second identical SMILES ->
    # dedups on resolved id (no validate call). The cached InChIKey input dedups
    # against existing_keys before any DB/PubChem work.
    session = _FakeSession(rows=[None])

    with patch(
        "app.services.input_validation.validate_compound",
        new=AsyncMock(return_value=canned),
    ) as mock_validate, patch(
        "app.services.input_validation.persist_validated_compounds",
        new=AsyncMock(return_value=1),
    ):
        result = await resolve_compounds(
            ["CC(=O)Oc1ccccc1C(=O)O", "CC(=O)Oc1ccccc1C(=O)O", "AAAAAAAAAAAAAA-BBBBBBBBBB-C"],
            existing_keys={resolved_id, existing_id},
            session=session,
            client=_client(),
        )

    # The first SMILES dedups against existing_keys (resolved_id already present),
    # so it is a duplicate too — nothing is valid.
    assert "CC(=O)Oc1ccccc1C(=O)O" in result.duplicates
    assert "AAAAAAAAAAAAAA-BBBBBBBBBB-C" in result.duplicates
    assert len(result.valid) == 0
    # The first SMILES still needed exactly one PubChem call to learn its id;
    # the second SMILES is byte-identical and dedups on the raw structure.
    assert mock_validate.await_count == 1
    _ = cached_existing  # built for clarity; not exec'd (deduped pre-DB)


# ---------------------------------------------------------------------------
# Test 5: unresolvable structure -> failed[].line 1-based, "not found in PubChem"
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unresolvable_structure_failed():
    session = _FakeSession(rows=[])

    with patch(
        "app.services.input_validation.validate_compound",
        new=AsyncMock(return_value=None),
    ) as mock_validate, patch(
        "app.services.input_validation.persist_validated_compounds",
        new=AsyncMock(return_value=0),
    ):
        result = await resolve_compounds(
            ["not-a-real-structure"],
            existing_keys=set(),
            session=session,
            client=_client(),
        )

    assert mock_validate.await_count == 1
    assert len(result.valid) == 0
    assert len(result.failed) == 1
    assert result.failed[0].line == 1
    assert result.failed[0].input == "not-a-real-structure"
    assert "not found in PubChem" in result.failed[0].reason
