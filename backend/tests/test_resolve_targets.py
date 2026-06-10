import uuid

import pytest

from app.integrations.uniprot import UniProtRecord
from app.services import canonical
from app.services.input_validation import resolve_target_accession, resolve_targets


class FakeTargetRepo:
    def __init__(self, by_key=None):
        self._by_key = by_key or {}

    async def get_by_key(self, key):
        return self._by_key.get(key)

    async def upsert(self, row):
        self._by_key[row["canonical_key"]] = type("T", (), row)

    async def source_id_by_name(self, name):
        return None


class FakeUniProt:
    def __init__(self, table):
        self._table = table

    async def resolve(self, acc):
        return self._table.get(acc.upper())

    async def resolve_symbol(self, sym):
        # map symbol -> accession via a reverse lookup over the table's gene_symbols
        for rec in self._table.values():
            if rec.gene_symbol == sym:
                return rec
        return None


@pytest.mark.asyncio
async def test_uniprot_accession_resolves_and_persists():
    up = FakeUniProt({"P04637": UniProtRecord("P04637", "TP53", "p53")})
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets([{"type": "uniprot", "value": "P04637"}], repo, up)
    assert not failed
    assert resolved[0].uniprot_accession == "P04637"
    assert resolved[0].gene_symbol == "TP53"
    assert resolved[0].canonical_key  # set


@pytest.mark.asyncio
async def test_symbol_resolves_via_resolve_symbol():
    up = FakeUniProt({"P04637": UniProtRecord("P04637", "TP53", "p53")})
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets([{"type": "symbol", "value": "tp53"}], repo, up)
    assert resolved and resolved[0].gene_symbol == "TP53"


@pytest.mark.asyncio
async def test_nonhuman_unresolved_lands_in_failed_with_line():
    up = FakeUniProt({})
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets([{"type": "uniprot", "value": "Q99999"}], repo, up)
    assert not resolved
    assert failed[0].reason and failed[0].line == 1


@pytest.mark.asyncio
async def test_malformed_accession_rejected():
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets(
        [{"type": "uniprot", "value": "??"}], repo, FakeUniProt({})
    )
    assert not resolved and "format" in failed[0].reason.lower()


@pytest.mark.asyncio
async def test_primary_and_secondary_accession_converge_to_one_target():
    # The same protein reached via its primary AND a secondary accession must resolve to
    # ONE canonical target_id — identity is keyed on the UniProt PRIMARY accession, so an
    # alias can never produce a duplicate row (the EGFR-duplicate bug).
    egfr = UniProtRecord("P00533", "EGFR", "Epidermal growth factor receptor")
    up = FakeUniProt({"P00533": egfr, "Q14225": egfr})  # both aliases -> same primary entry
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets(
        [{"type": "uniprot", "value": "P00533"}, {"type": "uniprot", "value": "Q14225"}],
        repo,
        up,
    )
    assert not failed
    assert len(resolved) == 1
    assert resolved[0].uniprot_accession == "P00533"


@pytest.mark.asyncio
async def test_resolve_target_accession_canonicalizes_on_primary():
    egfr = UniProtRecord("P00533", "EGFR", "Epidermal growth factor receptor")
    up = FakeUniProt({"P00533": egfr, "Q14225": egfr})
    repo = FakeTargetRepo()
    via_primary = await resolve_target_accession("P00533", repo, up)
    via_secondary = await resolve_target_accession("Q14225", repo, up)
    assert via_primary is not None and via_secondary is not None
    assert via_primary.target_id == via_secondary.target_id  # one entity, one id
    assert via_secondary.uniprot_accession == "P00533"  # stored under the primary


@pytest.mark.asyncio
async def test_resolve_target_accession_none_when_unresolvable():
    # A non-UniProt id (e.g. a ChEMBL target carrying a GenBank accession) -> skip, not crash.
    repo = FakeTargetRepo()
    assert await resolve_target_accession("AAI32679", repo, FakeUniProt({})) is None


@pytest.mark.asyncio
async def test_resolve_target_accession_db_fast_path_skips_uniprot():
    # A target already stored under its key is returned from the DB without a UniProt call.
    key = canonical.target_canonical_key(uniprot="P00533")
    row = {
        "target_id": uuid.UUID(canonical.target_id_from_key(key)),
        "canonical_key": key,
        "gene_symbol": "EGFR",
        "uniprot_accession": "P00533",
    }
    repo = FakeTargetRepo({key: type("T", (), row)})

    class BoomUniProt:
        async def resolve(self, acc):
            raise AssertionError("UniProt must not be called on a DB fast-path hit")

    rt = await resolve_target_accession("P00533", repo, BoomUniProt())
    assert rt is not None
    assert rt.uniprot_accession == "P00533"
    assert rt.validation_status == "db_hit"
