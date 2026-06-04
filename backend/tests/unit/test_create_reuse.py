# backend/tests/unit/test_create_reuse.py
"""Reuse guarantee: a CANONICAL KEY (UniProt accession / InChIKey) on create
resolves as a DB cache hit, so the provider (UniProt / PubChem) is NEVER called.

This locks the Task-6.3 contract: the dry-run review persists resolved entities,
then create reuses their canonical keys — every such key is a cache hit, no
re-enrichment. We drive the REAL ``resolve_*`` services (via the inject services)
with a stub session that returns a cached row, and assert the provider validator
is not invoked while ``injected == 1``.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _ExecResult:
    """Mimics ``await session.exec(stmt)`` — exposes ``.first()``."""

    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _CachedSession:
    """Async session stub: every DB-first lookup returns the SAME cached row.

    A single canonical-key input exercises exactly one lookup, so returning the
    row unconditionally models a cache hit without inspecting the statement.
    """

    def __init__(self, row):
        self._row = row

    async def exec(self, _stmt):
        return _ExecResult(self._row)

    def add(self, _obj):
        pass

    async def commit(self):
        pass


def _cached_target(gene, accession, protein_name="Cellular tumor antigen p53"):
    row = MagicMock()
    row.gene_symbol = gene
    row.uniprot_accession = accession
    row.protein_name = protein_name
    return row


def _cached_compound(inchikey):
    """A cached ``Compound`` row shaped enough for ``_compound_cache_dict``."""
    row = MagicMock()
    row.compound_id = str(uuid.uuid4())
    row.inchi_key = inchikey
    row.pubchem_cid = 702
    row.canonical_name = "Ethanol"
    row.canonical_key = f"inchikey:{inchikey}"
    return row


def _fake_run():
    run = MagicMock()
    run.analysis_id = uuid.uuid4()
    run.status = "pending"
    run.stage_results = {}
    run.parameters = {}
    return run


@pytest.mark.asyncio
async def test_inject_targets_accession_cache_hit_skips_uniprot():
    """``targets=['P04637']`` with a cached Target → UniProt validator NOT called,
    injected == 1 (the canonical accession is a pure DB cache hit)."""
    from app.services.manual_inputs import inject_targets_service

    session = _CachedSession(_cached_target("TP53", "P04637"))

    with patch("app.services.input_validation.validate_human_target",
               new=AsyncMock(side_effect=AssertionError("UniProt must not be called on a cache hit"))) as uniprot_spy, \
         patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock()), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()):
        resp = await inject_targets_service(
            targets=["P04637"],
            skip_validation=False,
            run=_fake_run(),
            session=session,
        )

    uniprot_spy.assert_not_called()
    assert resp.injected == 1


@pytest.mark.asyncio
async def test_inject_compounds_inchikey_cache_hit_skips_pubchem():
    """An InChIKey input with a cached Compound → PubChem validator NOT called,
    injected == 1 (the canonical InChIKey is a pure DB cache hit, no PubChem)."""
    from app.services.manual_inputs import inject_compounds_service

    inchikey = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"  # Ethanol
    session = _CachedSession(_cached_compound(inchikey))

    with patch("app.services.input_validation.validate_compound",
               new=AsyncMock(side_effect=AssertionError("PubChem must not be called on a cache hit"))) as pubchem_spy, \
         patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock()), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()):
        resp = await inject_compounds_service(
            compounds=[inchikey],
            run=_fake_run(),
            session=session,
        )

    pubchem_spy.assert_not_called()
    assert resp.injected == 1
