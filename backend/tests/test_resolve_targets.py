import pytest

from app.integrations.uniprot import UniProtRecord
from app.services.input_validation import resolve_targets


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
