import uuid

import pytest

from app.integrations.uniprot import UniProtReason, UniProtRecord, UniProtResolution
from app.services import canonical
from app.services.input_validation import resolve_target_accession, resolve_targets


class FakeTargetRepo:
    def __init__(self, by_key=None, by_symbol=None):
        self._by_key = by_key or {}
        self._by_symbol = by_symbol or {}

    async def get_by_key(self, key):
        return self._by_key.get(key)

    async def get_by_gene_symbol(self, gene_symbol):
        return self._by_symbol.get(gene_symbol)

    async def upsert(self, row):
        self._by_key[row["canonical_key"]] = type("T", (), row)

    async def source_id_by_name(self, name):
        return None


class FakeUniProt:
    def __init__(self, table):
        self._table = table

    async def resolve(self, acc):
        rec = self._table.get(acc.upper())
        if rec is not None:
            return UniProtResolution(record=rec, reason=None)
        return UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)

    async def resolve_symbol(self, sym):
        # map symbol -> accession via a reverse lookup over the table's gene_symbols
        for rec in self._table.values():
            if rec.gene_symbol == sym:
                return UniProtResolution(record=rec, reason=None)
        return UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)


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
async def test_gene_symbol_shaped_like_accession_resolves_via_symbol():
    # A real human gene symbol that happens to be 6-10 alphanumeric chars (TAS2R38, a taste
    # receptor, UniProt P59533) must be classified as a SYMBOL — NOT misread as a UniProt
    # accession. With no explicit type, the accession-shape test must be strict enough to let
    # it fall through to the gene-symbol resolver. (Loose "[A-Z0-9]{6,10}" wrongly matched it,
    # routing it to an accession lookup that 400s -> "not a human accession".)
    tas2r38 = UniProtRecord("P59533", "TAS2R38", "Taste receptor type 2 member 38")
    up = FakeUniProt({"P59533": tas2r38})
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets([{"value": "TAS2R38"}], repo, up)
    assert not failed
    assert resolved and resolved[0].uniprot_accession == "P59533"
    assert resolved[0].gene_symbol == "TAS2R38"


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
    via_primary = (await resolve_target_accession("P00533", repo, up)).target
    via_secondary = (await resolve_target_accession("Q14225", repo, up)).target
    assert via_primary is not None and via_secondary is not None
    assert via_primary.target_id == via_secondary.target_id  # one entity, one id
    assert via_secondary.uniprot_accession == "P00533"  # stored under the primary


@pytest.mark.asyncio
async def test_resolve_target_accession_invalid_id_reports_reason():
    # A non-UniProt id (e.g. a ChEMBL target carrying a GenBank accession) -> 400 -> skip,
    # not crash. The miss carries the INVALID_ID reason so the caller can word it honestly.
    repo = FakeTargetRepo()

    class FourHundredUniProt:
        async def resolve(self, acc):
            return UniProtResolution(None, UniProtReason.INVALID_ID)

    res = await resolve_target_accession("AAI32679", repo, FourHundredUniProt())
    assert res.target is None
    assert res.reason is UniProtReason.INVALID_ID


@pytest.mark.asyncio
async def test_resolve_target_accession_no_human_record_reports_reason():
    # A valid query with zero 9606 results -> NO_HUMAN_RECORD, surfaced to the caller.
    repo = FakeTargetRepo()
    res = await resolve_target_accession("Q99999", repo, FakeUniProt({}))
    assert res.target is None
    assert res.reason is UniProtReason.NO_HUMAN_RECORD


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

    res = await resolve_target_accession("P00533", repo, BoomUniProt())
    assert res.target is not None
    assert res.reason is None
    assert res.target.uniprot_accession == "P00533"
    assert res.target.validation_status == "db_hit"


@pytest.mark.asyncio
async def test_accession_invalid_id_reports_honest_message():
    # An accession-shaped input UniProt 400s on (not a resolvable UniProt query) must be
    # reported as "not a UniProt accession" — NOT conflated with a genuine no-human miss.
    class FourHundredUniProt:
        async def resolve(self, acc):
            return UniProtResolution(None, UniProtReason.INVALID_ID)

    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets(
        [{"type": "uniprot", "value": "P12345"}], repo, FourHundredUniProt()
    )
    assert not resolved
    assert failed[0].reason == "not a UniProt accession"
    assert failed[0].line == 1


@pytest.mark.asyncio
async def test_accession_no_human_record_reports_honest_message():
    # A valid UniProt query with zero 9606 results -> "no human (9606) UniProt record".
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets(
        [{"type": "uniprot", "value": "Q99999"}], repo, FakeUniProt({})
    )
    assert not resolved
    assert failed[0].reason == "no human (9606) UniProt record"
    assert failed[0].line == 1


# ---------------------------------------------------------------------------
# D6: non-UniProt-grammar accessions must be short-circuited before any
#     DB or network call (removes thousands of doomed round-trips in Stage 3).
# ---------------------------------------------------------------------------


class _CountingUniProt_d6:
    """Records whether resolve() was hit, so we can prove D6 avoids the network."""

    def __init__(self) -> None:
        self.calls = 0

    async def resolve(self, acc: str) -> UniProtResolution:
        self.calls += 1
        return UniProtResolution(None, UniProtReason.INVALID_ID)


class _EmptyRepo_d6:
    async def get_by_key(self, key):  # no DB hit
        return None

    async def source_id_by_name(self, name):
        return None

    async def upsert(self, row):  # pragma: no cover - not reached in this test
        return None


@pytest.mark.asyncio
async def test_resolve_target_accession_skips_non_uniprot_without_network():
    # A PubChem-BioAssay RefSeq/PDB/GenBank id is not a UniProt accession: it can neither key a
    # stored target (targets canonicalize on a UniProt primary) nor resolve via accession:/sec_acc:
    # (it 400s). It must be skipped with INVALID_ID and ZERO UniProt calls.
    up = _CountingUniProt_d6()
    res = await resolve_target_accession("NP_001234", _EmptyRepo_d6(), up, uniprot_source_id=None)
    assert res.target is None
    assert res.reason is UniProtReason.INVALID_ID
    assert up.calls == 0


@pytest.mark.asyncio
async def test_resolve_target_accession_still_calls_uniprot_for_real_accession():
    # A UniProt-grammar accession is NOT skipped — it proceeds to resolve (DB-miss -> network).
    up = _CountingUniProt_d6()
    res = await resolve_target_accession("P00533", _EmptyRepo_d6(), up, uniprot_source_id=None)
    assert up.calls == 1  # the guard does not block real accessions
    assert res.target is None  # _CountingUniProt_d6 returns no record, but the call was made


@pytest.mark.asyncio
async def test_unknown_symbol_reports_honest_message():
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets(
        [{"type": "symbol", "value": "NOTAGENE"}], repo, FakeUniProt({})
    )
    assert not resolved
    assert failed[0].reason == "not a recognized human (9606) gene symbol or UniProt accession"
    assert failed[0].line == 1


@pytest.mark.asyncio
async def test_resolve_targets_reports_inchikey_honestly():
    # A compound InChIKey pasted into a target box is not a UniProt accession and not a gene
    # symbol; it must be reported as such — NOT as a non-human/organism miss.
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets(
        [{"value": "RYYVLZVUVIJVGH-UHFFFAOYSA-N"}], repo, FakeUniProt({})
    )
    assert resolved == []
    assert len(failed) == 1
    assert "InChIKey" in failed[0].reason
    assert "human" not in failed[0].reason.lower() and "9606" not in failed[0].reason
    assert failed[0].line == 1


@pytest.mark.asyncio
async def test_resolve_targets_unknown_symbol_does_not_blame_organism():
    # An unresolvable, non-InChIKey token is an unrecognized identifier, not an organism problem.
    repo = FakeTargetRepo()
    resolved, failed = await resolve_targets([{"value": "NOTAGENE123"}], repo, FakeUniProt({}))
    assert resolved == []
    assert failed[0].reason == "not a recognized human (9606) gene symbol or UniProt accession"


@pytest.mark.asyncio
async def test_known_symbol_db_first_skips_uniprot():
    # A gene symbol whose target is already stored (any prior run) resolves to its accession
    # via the DB — the UniProt client's resolve_symbol/resolve must NOT be called (G-4).
    key = canonical.target_canonical_key(uniprot="P04637")
    row = {
        "target_id": uuid.UUID(canonical.target_id_from_key(key)),
        "canonical_key": key,
        "gene_symbol": "TP53",
        "uniprot_accession": "P04637",
    }
    stored = type("T", (), row)
    repo = FakeTargetRepo(by_key={key: stored}, by_symbol={"TP53": stored})

    class CountingUniProt:
        def __init__(self):
            self.resolve_calls = 0
            self.symbol_calls = 0

        async def resolve(self, acc):  # pragma: no cover - asserted to be 0
            self.resolve_calls += 1
            return UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)

        async def resolve_symbol(self, sym):  # pragma: no cover - asserted to be 0
            self.symbol_calls += 1
            return UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)

    up = CountingUniProt()
    resolved, failed = await resolve_targets([{"type": "symbol", "value": "tp53"}], repo, up)
    assert not failed
    assert resolved and resolved[0].uniprot_accession == "P04637"
    assert resolved[0].gene_symbol == "TP53"
    assert up.resolve_calls == 0
    assert up.symbol_calls == 0
