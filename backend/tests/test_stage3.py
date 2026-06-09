import uuid

import pytest

from app.pipeline.stages import stage3
from app.services import canonical


class FakeChembl:
    def __init__(self, table):
        self.table = table

    async def targets_for_inchikey(self, ik, *, min_pchembl, min_confidence):
        from app.integrations.chembl import ChemblHit

        return [ChemblHit(a, p, "IC50") for a, p in self.table.get(ik, [])]


class FakePubchem:
    def __init__(self, table):
        self.table = table

    async def active_targets_for_inchikey(self, ik):
        return self.table.get(ik, [])


async def _resolve_all(accession):
    key = canonical.target_canonical_key(uniprot=accession)
    return uuid.UUID(canonical.target_id_from_key(key)), accession, key


@pytest.mark.asyncio
async def test_union_dedupe_precedence_and_coverage():
    compounds = [
        {
            "compound_id": "11111111-1111-5111-8111-111111111111",
            "inchi_key": "IKA",
            "canonical_name": "A",
        },
        {
            "compound_id": "22222222-2222-5222-8222-222222222222",
            "inchi_key": "IKB",
            "canonical_name": "B",
        },
    ]
    chembl = FakeChembl({"IKA": [("P04637", 6.0)]})
    pubchem = FakePubchem({"IKA": ["P04637", "Q00001"]})
    result = await stage3.compute(
        compounds,
        chembl,
        pubchem,
        resolve_target=_resolve_all,
        min_pchembl=5.0,
        min_confidence=7,
    )
    methods = {(e["uniprot_accession"], e["prediction_method"]) for e in result["compound_targets"]}
    assert ("P04637", "chembl_bioactivity") in methods  # ChEMBL wins the shared pair
    assert ("Q00001", "pubchem_bioassay") in methods  # PubChem-only kept
    assert result["per_compound"]["11111111-1111-5111-8111-111111111111"]["coverage"] == 2
    assert result["per_compound"]["22222222-2222-5222-8222-222222222222"]["coverage"] == 0
    assert result["coverage_pct"] == 50.0


@pytest.mark.asyncio
async def test_nonhuman_accession_skipped():
    # resolver returns None for the PubChem accession -> skipped, not counted, no edge.
    async def _resolve_human_only(acc):
        if acc == "NONHUMAN":
            return None
        key = canonical.target_canonical_key(uniprot=acc)
        return uuid.UUID(canonical.target_id_from_key(key)), acc, key

    compounds = [
        {
            "compound_id": "11111111-1111-5111-8111-111111111111",
            "inchi_key": "IKA",
            "canonical_name": "A",
        }
    ]
    chembl = FakeChembl({"IKA": [("P04637", 6.0)]})
    pubchem = FakePubchem({"IKA": ["NONHUMAN"]})
    result = await stage3.compute(
        compounds,
        chembl,
        pubchem,
        resolve_target=_resolve_human_only,
        min_pchembl=5.0,
        min_confidence=7,
    )
    accs = {e["uniprot_accession"] for e in result["compound_targets"]}
    assert accs == {"P04637"}
    assert result["per_compound"]["11111111-1111-5111-8111-111111111111"]["coverage"] == 1
