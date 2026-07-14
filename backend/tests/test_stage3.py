import logging
import uuid

import pytest

from app.pipeline.stages import stage3
from app.pipeline.stages.stage3 import _reuse_edges
from app.services import canonical


class FakeChembl:
    def __init__(self, table):
        self.table = table

    async def targets_for_inchikey(self, ik, *, min_pchembl, min_confidence, connectivity_key=None):
        from app.integrations.chembl import ChemblHit

        return [ChemblHit(a, p, "IC50") for a, p in self.table.get(ik, [])]


class FakePubchem:
    def __init__(self, table):
        self.table = table

    async def active_targets_for_inchikey(self, ik):
        return self.table.get(ik, [])


async def _resolve_all(accession):
    key = canonical.target_canonical_key(uniprot=accession)
    return uuid.UUID(canonical.target_id_from_key(key)), accession


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
        return uuid.UUID(canonical.target_id_from_key(key)), acc

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


@pytest.mark.asyncio
async def test_coverage_counts_distinct_targets_not_accessions():
    # ChEMBL reports the primary (P04637); PubChem reports a SECONDARY accession (Q14225) of the
    # SAME protein. Both resolve to one target_id -> coverage must be 1 (distinct targets), and a
    # single edge is emitted with ChEMBL winning the precedence.
    async def _resolve_alias(acc):
        primary = "P04637" if acc in ("P04637", "Q14225") else acc
        key = canonical.target_canonical_key(uniprot=primary)
        return uuid.UUID(canonical.target_id_from_key(key)), "TP53"

    compounds = [
        {
            "compound_id": "11111111-1111-5111-8111-111111111111",
            "inchi_key": "IKA",
            "canonical_name": "A",
        }
    ]
    chembl = FakeChembl({"IKA": [("P04637", 6.0)]})
    pubchem = FakePubchem({"IKA": ["Q14225"]})
    result = await stage3.compute(
        compounds,
        chembl,
        pubchem,
        resolve_target=_resolve_alias,
        min_pchembl=5.0,
        min_confidence=7,
    )
    cid = "11111111-1111-5111-8111-111111111111"
    assert result["per_compound"][cid]["coverage"] == 1  # one distinct target, not two accessions
    edges = result["compound_targets"]
    assert len(edges) == 1  # one edge per (compound, target)
    assert edges[0]["prediction_method"] == "chembl_bioactivity"  # ChEMBL wins


@pytest.mark.asyncio
async def test_targets_carry_gene_symbol_and_accession():
    """Each target row in compute() output must expose gene_symbol + uniprot_accession."""

    async def _resolve(acc):
        if acc == "P00533":
            key = canonical.target_canonical_key(uniprot="P00533")
            return uuid.UUID(canonical.target_id_from_key(key)), "EGFR"
        return None

    compounds = [
        {
            "compound_id": "11111111-1111-1111-1111-111111111111",
            "inchi_key": "IK",
            "canonical_name": "TestCompound",
        }
    ]
    chembl = FakeChembl({"IK": [("P00533", 6.5)]})
    pubchem = FakePubchem({})
    result = await stage3.compute(
        compounds,
        chembl,
        pubchem,
        resolve_target=_resolve,
        min_pchembl=5.0,
        min_confidence=8,
    )
    assert len(result["targets"]) == 1
    t = result["targets"][0]
    assert t["gene_symbol"] == "EGFR"
    assert t["uniprot_accession"] == "P00533"
    assert t["canonical_name"] == "EGFR"  # gene or acc, unchanged semantics


def _edge(method="chembl_bioactivity", pchembl=6.0, mp=5.0, mc=7):
    return {
        "target_id": "t1",
        "prediction_method": method,
        "pchembl_value": pchembl,
        "min_pchembl": mp,
        "min_assay_confidence": mc,
        "gene_symbol": "TP53",
        "uniprot_accession": "P04637",
        "source_url": "u",
    }


def test_reuse_when_confidence_matches_and_pchembl_not_looser():
    cached = [_edge(pchembl=6.0, mp=5.0, mc=7)]
    out = stage3._reuse_edges(cached, min_pchembl=5.0, min_confidence=7)
    assert out is not None and len(out) == 1


def test_reuse_refilters_pchembl_when_run_is_stricter():
    cached = [_edge(pchembl=5.5, mp=5.0, mc=7), _edge(pchembl=6.5, mp=5.0, mc=7)]
    out = stage3._reuse_edges(cached, min_pchembl=6.0, min_confidence=7)
    assert out is not None and [e["pchembl_value"] for e in out] == [6.5]


def test_refetch_when_run_pchembl_looser_than_discovery():
    cached = [_edge(pchembl=6.0, mp=5.0, mc=7)]
    assert stage3._reuse_edges(cached, min_pchembl=3.0, min_confidence=7) is None


def test_refetch_when_confidence_differs():
    cached = [_edge(mc=7)]
    assert stage3._reuse_edges(cached, min_pchembl=5.0, min_confidence=9) is None


def test_refetch_when_no_cached_edges():
    assert stage3._reuse_edges([], min_pchembl=5.0, min_confidence=7) is None


def test_refetch_when_legacy_null_params():
    cached = [_edge(mp=None, mc=None)]
    assert stage3._reuse_edges(cached, min_pchembl=5.0, min_confidence=7) is None


def test_reuse_edges_logs_legacy_null_param_refetch(caplog):
    cached = [
        {
            "target_id": "t1",
            "prediction_method": "chembl_bioactivity",
            "min_assay_confidence": 8,
            "min_pchembl": None,  # legacy null-param edge
        }
    ]
    with caplog.at_level(logging.DEBUG, logger="herbaflow.pipeline"):
        result = _reuse_edges(cached, min_pchembl=6.0, min_confidence=8)
    assert result is None
    assert any("legacy null-param" in r.message for r in caplog.records)
