import pytest
from uuid import uuid4
from analysis.models import AdmeParams, CompoundRecord
from analysis.stages.stage2_adme import filter_compounds


def make_compound(**kwargs) -> CompoundRecord:
    defaults = dict(
        compound_id=uuid4(),
        canonical_name="test",
        smiles=None,
        chembl_id=None,
        pubchem_cid=None,
        molecular_weight=300.0,
        logp=2.0,
        hbond_donors=2,
        hbond_acceptors=4,
        tpsa=60.0,
        rotatable_bonds=5,
        np_likeness_score=0.3,
        num_ro5_violations=0,
    )
    defaults.update(kwargs)
    return CompoundRecord(**defaults)


def test_passes_all_filters():
    compound = make_compound()
    params = AdmeParams()
    result = filter_compounds([compound], params)
    assert result["passed"][0].compound_id == compound.compound_id
    assert result["failed"] == []
    assert result["np_exceptions"] == []


def test_fails_mw():
    compound = make_compound(molecular_weight=600.0)
    result = filter_compounds([compound], AdmeParams())
    assert result["failed"][0].compound_id == compound.compound_id


def test_fails_logp():
    compound = make_compound(logp=6.0)
    result = filter_compounds([compound], AdmeParams())
    assert len(result["failed"]) == 1


def test_np_exception_flagged_not_excluded():
    # Compound fails MW but has high np_likeness_score — should go to np_exceptions
    compound = make_compound(molecular_weight=700.0, np_likeness_score=0.8)
    result = filter_compounds([compound], AdmeParams(np_exception_threshold=0.5))
    assert result["passed"] == []
    assert result["np_exceptions"][0].compound_id == compound.compound_id
    assert result["failed"] == []


def test_veber_filter():
    compound = make_compound(tpsa=200.0, rotatable_bonds=15)
    result = filter_compounds([compound], AdmeParams(apply_veber=True))
    assert len(result["failed"]) == 1


def test_veber_not_applied_when_disabled():
    compound = make_compound(tpsa=200.0, rotatable_bonds=15)
    result = filter_compounds([compound], AdmeParams(apply_veber=False))
    assert len(result["passed"]) == 1


def test_missing_mw_skips_mw_filter():
    compound = make_compound(molecular_weight=None)
    result = filter_compounds([compound], AdmeParams())
    # Can't evaluate MW filter — compound passes
    assert len(result["passed"]) == 1
