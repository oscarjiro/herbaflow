import uuid

import pytest
from sqlalchemy import select, text

from app.integrations.chembl import ChemblHit
from app.integrations.uniprot import UniProtReason, UniProtRecord, UniProtResolution
from app.models.compound_target import CompoundTarget
from app.models.target import Target
from app.pipeline.stages import stage3


class FakeChembl:
    def __init__(self, table):
        self.table = table

    async def targets_for_inchikey(self, ik, *, min_pchembl, min_confidence):
        return [ChemblHit(a, p, "IC50") for a, p in self.table.get(ik, [])]


class FakePubchem:
    def __init__(self, table):
        self.table = table

    async def active_targets_for_inchikey(self, ik):
        return self.table.get(ik, [])


class FakeUniProt:
    def __init__(self, table):
        self.table = table

    async def resolve(self, accession):
        rec = self.table.get(accession)
        if rec is not None:
            return UniProtResolution(rec, None)
        return UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)


@pytest.mark.asyncio
async def test_stage3_persists_targets_and_measured_edges(session):
    # Seed the source rows (not applied by the integration migrations).
    await session.execute(
        text(
            "insert into source_systems(source_name, source_type) values "
            "('ChEMBL', 'api'),('PubChem BioAssay', 'api'),('UniProt', 'api') "
            "on conflict (source_name) do nothing"
        )
    )
    # Two compounds: one with a ChEMBL hit, one whose InChIKey yields nothing.
    c_hit = uuid.uuid4()
    c_none = uuid.uuid4()
    await session.execute(
        text(
            "insert into compounds"
            "(compound_id, canonical_key, canonical_name, validation_status, inchi_key) values "
            "(:h, 'inchikey:IKHIT', 'HitComp', 'externally_validated', 'IKHIT'),"
            "(:n, 'inchikey:IKNONE', 'NoneComp', 'externally_validated', 'IKNONE')"
        ),
        {"h": c_hit, "n": c_none},
    )
    await session.flush()

    fake_chembl = FakeChembl({"IKHIT": [("P04637", 6.5)]})
    fake_pubchem = FakePubchem({})
    fake_uniprot = FakeUniProt({"P04637": UniProtRecord("P04637", "TP53", "p53")})

    result = await stage3.run(
        session,
        [{"compound_id": str(c_hit)}, {"compound_id": str(c_none)}],
        {"min_pchembl": 5.0, "min_assay_confidence": 7},
        chembl=fake_chembl,
        pubchem=fake_pubchem,
        uniprot=fake_uniprot,
    )
    await session.flush()

    # Target P04637 persisted with the UniProt gene symbol.
    target_row = (
        await session.execute(select(Target).where(Target.canonical_key == "uniprot:P04637"))
    ).scalar_one()
    assert target_row.gene_symbol == "TP53"

    # A chembl_bioactivity edge persisted for the hit compound.
    edge_row = (
        await session.execute(select(CompoundTarget).where(CompoundTarget.compound_id == c_hit))
    ).scalar_one()
    assert edge_row.prediction_method == "chembl_bioactivity"
    assert edge_row.target_id == target_row.target_id
    assert edge_row.pchembl_value == 6.5

    # The no-target compound is surfaced (coverage 0), never gated; 50% overall coverage.
    assert result["per_compound"][str(c_none)]["coverage"] == 0
    assert result["coverage_pct"] == 50.0
