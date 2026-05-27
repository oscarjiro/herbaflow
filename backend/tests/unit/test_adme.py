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
    # Only MW is None but other properties are present — the compound has
    # enough data to evaluate and should pass the remaining checks.
    compound = make_compound(molecular_weight=None)
    result = filter_compounds([compound], AdmeParams())
    assert len(result["passed"]) == 1


def test_adme_compound_all_none_properties_fails():
    """A compound with no ADME data should not auto-pass screening."""
    compound = make_compound(
        molecular_weight=None,
        logp=None,
        hbond_donors=None,
        hbond_acceptors=None,
        tpsa=None,
        rotatable_bonds=None,
        np_likeness_score=None,
    )
    result = filter_compounds([compound], AdmeParams())
    assert result["passed"] == [], "all-None compound must not auto-pass"
    assert result["np_exceptions"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0].compound_id == compound.compound_id


def test_adme_compound_all_none_not_in_active_ids():
    """All-None compound must not appear in any active (passed/np) ID set."""
    compound = make_compound(
        molecular_weight=None,
        logp=None,
        hbond_donors=None,
        hbond_acceptors=None,
        tpsa=None,
        rotatable_bonds=None,
        np_likeness_score=None,
    )
    result = filter_compounds([compound], AdmeParams())
    cid = str(compound.compound_id)
    active_ids = [str(c.compound_id) for c in result["passed"] + result["np_exceptions"]]
    assert cid not in active_ids


def test_manual_compound_bypasses_adme_when_flag_disabled():
    """When apply_adme_to_manual=False, user_provided compounds skip ADME and get adme_pass=True.

    Scientific basis: Lipinski CA et al. Adv Drug Deliv Rev. 2001.
    Pre-screened compounds from published ADME studies should not be re-filtered.
    """
    # A compound that would clearly FAIL Lipinski rules (mw > 500, logp > 5)
    compound = make_compound(
        molecular_weight=900.0,  # violates max_mw=500
        logp=8.0,                # violates max_logp=5
        source="user_provided",
    )
    params = AdmeParams(apply_adme_to_manual=False)
    result = filter_compounds([compound], params)

    # Must pass unconditionally
    assert len(result["passed"]) == 1, "user_provided compound must bypass ADME and pass"
    assert result["failed"] == []
    assert result["np_exceptions"] == []
    assert result["passed"][0].compound_id == compound.compound_id


def test_manual_compound_screened_when_flag_enabled():
    """Default: user_provided compounds ARE screened by ADME (apply_adme_to_manual=True)."""
    # A compound that clearly FAILS Lipinski rules
    compound = make_compound(
        molecular_weight=900.0,  # violates max_mw=500
        logp=8.0,                # violates max_logp=5
        source="user_provided",
    )
    params = AdmeParams(apply_adme_to_manual=True)  # default
    result = filter_compounds([compound], params)

    # Must fail — default behaviour is unchanged
    assert result["passed"] == []
    assert result["np_exceptions"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0].compound_id == compound.compound_id
