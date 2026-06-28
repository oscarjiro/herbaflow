"""Unit tests for the resolve_compounds engine (every branch, with fakes)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.integrations.pubchem import PubChemRecord
from app.schemas.compound import CompoundInput
from app.services.input_validation import resolve_compounds

# Ethanol: SMILES "CCO" -> InChIKey LFQSCWFLJHTTHZ-UHFFFAOYSA-N (RDKit, deterministic).
ETHANOL_SMILES = "CCO"
ETHANOL_INCHIKEY = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
ETHANOL_KEY = f"inchikey:{ETHANOL_INCHIKEY}"

MANUAL_SOURCE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@dataclass
class FakeCompound:
    """Stand-in for the Compound ORM row returned by repo.get_by_key."""

    compound_id: uuid.UUID
    canonical_key: str
    canonical_name: str | None
    validation_status: str
    pubchem_cid: str | None = None


class FakeRepo:
    def __init__(self, existing: dict[str, FakeCompound] | None = None) -> None:
        self._existing = existing or {}
        self.upserted: list[dict[str, Any]] = []
        self.manual_source_calls = 0

    async def get_by_key(self, canonical_key: str) -> FakeCompound | None:
        return self._existing.get(canonical_key)

    async def upsert(self, row: dict[str, Any]) -> None:
        self.upserted.append(row)

    async def manual_source_id(self) -> uuid.UUID | None:
        self.manual_source_calls += 1
        return MANUAL_SOURCE_ID


@dataclass
class FakePubChem:
    record: PubChemRecord | None = None
    calls: list[str] = field(default_factory=list)

    async def fetch_by_inchikey(self, inchikey: str) -> PubChemRecord | None:
        self.calls.append(inchikey)
        return self.record


def _pubchem_record() -> PubChemRecord:
    return PubChemRecord(
        pubchem_cid="702",
        smiles="CCO",
        molecular_formula="C2H6O",
        molecular_weight=46.07,
        name="ethanol",
    )


@pytest.mark.asyncio
async def test_smiles_already_in_db_reused_no_pubchem() -> None:
    """Scenario 1: SMILES already in DB -> reused, PubChem not called, nothing upserted."""
    db_row = FakeCompound(
        compound_id=uuid.uuid4(),
        canonical_key=ETHANOL_KEY,
        canonical_name="ethanol",
        validation_status="externally_validated",
        pubchem_cid="702",
    )
    repo = FakeRepo({ETHANOL_KEY: db_row})
    pubchem = FakePubChem(record=_pubchem_record())

    resolved, failed = await resolve_compounds(
        [CompoundInput(type="smiles", value=ETHANOL_SMILES)], repo, pubchem
    )

    assert len(resolved) == 1
    assert failed == []
    r = resolved[0]
    assert r.compound_id == db_row.compound_id
    assert r.canonical_key == ETHANOL_KEY
    assert r.canonical_name == "ethanol"
    assert r.pubchem_cid == "702"
    assert r.validation_status == "externally_validated"
    assert len(pubchem.calls) == 0
    assert repo.upserted == []


@pytest.mark.asyncio
async def test_smiles_not_in_db_pubchem_hit_externally_validated() -> None:
    """Scenario 2: not in DB + PubChem hit -> upsert externally_validated with cid + smiles."""
    repo = FakeRepo()
    pubchem = FakePubChem(record=_pubchem_record())

    resolved, failed = await resolve_compounds(
        [CompoundInput(type="smiles", value=ETHANOL_SMILES)], repo, pubchem
    )

    assert failed == []
    assert len(resolved) == 1
    assert pubchem.calls == [ETHANOL_INCHIKEY]
    assert len(repo.upserted) == 1
    row = repo.upserted[0]
    assert row["validation_status"] == "externally_validated"
    assert row["canonical_key"] == ETHANOL_KEY
    assert row["pubchem_cid"] == "702"
    assert row["smiles"] == "CCO"
    assert row["molecular_formula"] == "C2H6O"
    assert row["molecular_weight"] == 46.07
    assert row["source_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/702"
    assert row["retrieved_at"] is not None
    r = resolved[0]
    assert r.validation_status == "externally_validated"
    assert r.canonical_name == "ethanol"
    assert r.canonical_key == ETHANOL_KEY
    assert r.pubchem_cid == "702"


@pytest.mark.asyncio
async def test_smiles_not_in_db_pubchem_miss_structure_only() -> None:
    """Scenario 3: not in DB + PubChem miss -> structure_only, manual source, null descriptors."""
    repo = FakeRepo()
    pubchem = FakePubChem(record=None)

    resolved, failed = await resolve_compounds(
        [CompoundInput(type="smiles", value=ETHANOL_SMILES)], repo, pubchem
    )

    assert failed == []
    assert len(resolved) == 1
    assert pubchem.calls == [ETHANOL_INCHIKEY]
    assert len(repo.upserted) == 1
    row = repo.upserted[0]
    assert row["validation_status"] == "structure_only"
    # smiles is the RDKit canonical SMILES for ethanol.
    assert row["smiles"] == "CCO"
    assert row["inchi_key"] == ETHANOL_INCHIKEY
    assert row["source_id"] == MANUAL_SOURCE_ID
    # Descriptor / external fields must be absent or None.
    assert row.get("pubchem_cid") is None
    assert row.get("molecular_formula") is None
    assert row.get("molecular_weight") is None
    assert repo.manual_source_calls == 1
    r = resolved[0]
    assert r.validation_status == "structure_only"


@pytest.mark.asyncio
async def test_inchikey_in_db_reused_no_pubchem() -> None:
    """Scenario 4: bare InChIKey present in DB -> reused, no PubChem, nothing upserted."""
    db_row = FakeCompound(
        compound_id=uuid.uuid4(),
        canonical_key=ETHANOL_KEY,
        canonical_name="ethanol",
        validation_status="externally_validated",
        pubchem_cid="702",
    )
    repo = FakeRepo({ETHANOL_KEY: db_row})
    pubchem = FakePubChem(record=_pubchem_record())

    resolved, failed = await resolve_compounds(
        [CompoundInput(type="inchikey", value=ETHANOL_INCHIKEY)], repo, pubchem
    )

    assert failed == []
    assert len(resolved) == 1
    assert resolved[0].compound_id == db_row.compound_id
    assert resolved[0].pubchem_cid == "702"
    assert len(pubchem.calls) == 0
    assert repo.upserted == []


@pytest.mark.asyncio
async def test_bare_inchikey_db_miss_pubchem_miss_failed() -> None:
    """Scenario 5: bare InChIKey not in DB and not in PubChem -> failed, mentions SMILES."""
    repo = FakeRepo()
    pubchem = FakePubChem(record=None)

    resolved, failed = await resolve_compounds(
        [CompoundInput(type="inchikey", value=ETHANOL_INCHIKEY)], repo, pubchem
    )

    assert resolved == []
    assert len(failed) == 1
    assert failed[0].value == ETHANOL_INCHIKEY
    assert "SMILES" in failed[0].reason
    assert pubchem.calls == [ETHANOL_INCHIKEY]
    assert repo.upserted == []


@pytest.mark.asyncio
async def test_malformed_smiles_failed_invalid_structure() -> None:
    """Scenario 6: garbage SMILES -> failed with 'invalid structure', nothing upserted."""
    repo = FakeRepo()
    pubchem = FakePubChem(record=_pubchem_record())

    resolved, failed = await resolve_compounds(
        [CompoundInput(type="smiles", value="not-a-molecule!!")], repo, pubchem
    )

    assert resolved == []
    assert len(failed) == 1
    assert failed[0].value == "not-a-molecule!!"
    assert failed[0].reason == "invalid structure"
    assert pubchem.calls == []
    assert repo.upserted == []


@pytest.mark.asyncio
async def test_duplicate_inputs_yield_single_resolved() -> None:
    """Scenario 7: same molecule twice -> exactly one resolved entry, one upsert."""
    repo = FakeRepo()
    pubchem = FakePubChem(record=_pubchem_record())

    resolved, failed = await resolve_compounds(
        [
            CompoundInput(type="smiles", value=ETHANOL_SMILES),
            CompoundInput(type="smiles", value=ETHANOL_SMILES),
        ],
        repo,
        pubchem,
    )

    assert failed == []
    assert len(resolved) == 1
    # Only resolved once -> only one upsert and one pubchem lookup.
    assert len(repo.upserted) == 1
    assert pubchem.calls == [ETHANOL_INCHIKEY]


@pytest.mark.asyncio
async def test_malformed_inchikey_typed_failed() -> None:
    """Bonus: token typed as inchikey but not a valid InChIKey -> failed, nothing upserted."""
    repo = FakeRepo()
    pubchem = FakePubChem(record=_pubchem_record())

    resolved, failed = await resolve_compounds(
        [CompoundInput(type="inchikey", value="NOT-A-KEY")], repo, pubchem
    )

    assert resolved == []
    assert len(failed) == 1
    assert failed[0].value == "NOT-A-KEY"
    assert failed[0].reason == "invalid InChIKey format"
    assert pubchem.calls == []
    assert repo.upserted == []


@pytest.mark.asyncio
async def test_resolve_compounds_records_line_on_failure() -> None:
    """Line index (1-based) is recorded on every compound resolution failure."""
    repo = FakeRepo()
    pubchem = FakePubChem(record=None)

    # Line 1 is blank (skipped, no failure); line 2 is an invalid SMILES structure.
    inputs = [CompoundInput(value=""), CompoundInput(value="@@@not-a-smiles@@@")]
    resolved, failed = await resolve_compounds(inputs, repo=repo, pubchem=pubchem)

    assert resolved == []
    assert len(failed) == 1
    assert failed[0].line == 2


# ---------------------------------------------------------------------------
# Dedup by identity + phased batch-resolve: identical inputs resolve once,
# two SMILES collapsing to the same InChIKey are treated as one compound, and
# repeated invalid tokens still generate one FailedInput per original line.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_identical_smiles_one_pubchem_call(monkeypatch) -> None:
    """50 identical SMILES trigger one RDKit identity call, one PubChem lookup, one upsert."""
    from app.services import structure as structure_mod

    call_count: dict[str, int] = {"n": 0}
    orig = structure_mod.identity_from_smiles

    def spy(smiles: str):
        call_count["n"] += 1
        return orig(smiles)

    monkeypatch.setattr(structure_mod, "identity_from_smiles", spy)

    repo = FakeRepo()
    pubchem = FakePubChem(record=_pubchem_record())

    resolved, failed = await resolve_compounds(
        [CompoundInput(type="smiles", value=ETHANOL_SMILES) for _ in range(50)],
        repo,
        pubchem,
    )

    assert not failed
    assert len(resolved) == 1
    assert call_count["n"] == 1  # one RDKit call per distinct raw token, not per input line
    assert len(pubchem.calls) == 1
    assert pubchem.calls[0] == ETHANOL_INCHIKEY
    assert len(repo.upserted) == 1


@pytest.mark.asyncio
async def test_two_smiles_same_inchikey_collapse() -> None:
    """Two different SMILES strings that map to the same InChIKey produce one resolved compound."""
    # "OCC" is an alternative input traversal of ethanol; RDKit canonicalises it to the same
    # InChIKey as "CCO", so the two inputs must collapse to a single work item.
    ETHANOL_ALT = "OCC"
    repo = FakeRepo()
    pubchem = FakePubChem(record=_pubchem_record())

    resolved, failed = await resolve_compounds(
        [
            CompoundInput(type="smiles", value=ETHANOL_SMILES),
            CompoundInput(type="smiles", value=ETHANOL_ALT),
        ],
        repo,
        pubchem,
    )

    assert not failed
    assert len(resolved) == 1
    assert resolved[0].canonical_key == ETHANOL_KEY
    assert len(pubchem.calls) == 1
    assert len(repo.upserted) == 1


@pytest.mark.asyncio
async def test_failed_compound_lines_preserved_under_dedup() -> None:
    """Repeated identical invalid SMILES each produce their own FailedInput with the right line."""
    BAD = "not-a-molecule!!"
    repo = FakeRepo()
    pubchem = FakePubChem(record=None)

    inputs = [
        CompoundInput(type="smiles", value=BAD),  # line 1
        CompoundInput(type="smiles", value=BAD),  # line 2
        CompoundInput(type="smiles", value=BAD),  # line 3
    ]
    resolved, failed = await resolve_compounds(inputs, repo, pubchem)

    assert resolved == []
    assert len(failed) == 3
    assert [f.line for f in failed] == [1, 2, 3]
    assert all(f.reason == "invalid structure" for f in failed)
    assert len(pubchem.calls) == 0


class _ConcurrencySpyPubChem:
    """Tracks peak concurrent in-flight PubChem calls to prove the network fan-out."""

    def __init__(self, record) -> None:
        self.record = record
        self.calls: list[str] = []
        self._in_flight = 0
        self.max_in_flight = 0

    async def fetch_by_inchikey(self, inchikey: str):
        self.calls.append(inchikey)
        self._in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self._in_flight)
        await asyncio.sleep(0)  # yield so siblings can overlap if launched concurrently
        self._in_flight -= 1
        return self.record


class _ConcurrencySpyRepo:
    """Tracks peak concurrent DB ops to prove the single session stays serial."""

    def __init__(self) -> None:
        self._existing: dict = {}
        self.upserted: list = []
        self._in_flight = 0
        self.max_db_in_flight = 0

    async def _touch(self) -> None:
        self._in_flight += 1
        self.max_db_in_flight = max(self.max_db_in_flight, self._in_flight)
        await asyncio.sleep(0)
        self._in_flight -= 1

    async def get_by_key(self, key: str):
        await self._touch()
        return self._existing.get(key)

    async def upsert(self, row: dict) -> None:
        await self._touch()
        self._existing[row["canonical_key"]] = row
        self.upserted.append(row)

    async def manual_source_id(self):
        await self._touch()
        return MANUAL_SOURCE_ID


@pytest.mark.asyncio
async def test_compound_misses_resolved_concurrently() -> None:
    """N distinct DB-miss compounds: PubChem calls fan out concurrently; DB stays serial."""
    pubchem = _ConcurrencySpyPubChem(record=_pubchem_record())
    repo = _ConcurrencySpyRepo()

    # Three distinct SMILES -> three distinct canonical keys -> three PubChem misses.
    inputs = [
        CompoundInput(type="smiles", value="CCO"),  # ethanol
        CompoundInput(type="smiles", value="C"),  # methane
        CompoundInput(type="smiles", value="CC"),  # ethane
    ]
    resolved, failed = await resolve_compounds(inputs, repo, pubchem)

    assert not failed
    assert len(resolved) == 3
    assert pubchem.max_in_flight > 1  # PubChem fetches overlapped (proves asyncio.gather)
    assert repo.max_db_in_flight == 1  # DB ops stayed serial on the one session
