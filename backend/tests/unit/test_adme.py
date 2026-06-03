import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from analysis.models import AdmeParams, CompoundRecord, PipelineConfig
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
    """When apply_adme_to_manual=False, user_provided compounds skip ADME and land in 'bypassed'.

    Scientific basis: Lipinski CA et al. Adv Drug Deliv Rev. 2001.
    Pre-screened compounds from published ADME studies should not be re-filtered,
    but they must be reported honestly as bypassed, not as having passed screening.
    """
    # A compound that would clearly FAIL Lipinski rules (mw > 500, logp > 5)
    compound = make_compound(
        molecular_weight=900.0,  # violates max_mw=500
        logp=8.0,                # violates max_logp=5
        source="user_provided",
    )
    params = AdmeParams(apply_adme_to_manual=False)
    result = filter_compounds([compound], params)

    # Bypassed manual compound goes to its own bucket, not "passed"
    assert result["bypassed"][0].compound_id == compound.compound_id
    assert result["passed"] == []
    assert result["failed"] == []
    assert result["np_exceptions"] == []


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


def test_apply_pains_removed_from_adme_params():
    """PAINS is reported as an annotation, never a filter param."""
    params = AdmeParams()
    assert not hasattr(params, "apply_pains")


def _manual_compound(**kw):
    base = dict(compound_id="c1", canonical_name="x", smiles="C", chembl_id=None,
                pubchem_cid=1, molecular_weight=900.0, logp=9.0, hbond_donors=0,
                hbond_acceptors=0, tpsa=0.0, rotatable_bonds=0, np_likeness_score=0.0,
                is_pains_positive=False, num_ro5_violations=0, source="user_provided")
    base.update(kw)
    return CompoundRecord(**base)


def test_manual_bypassed_when_toggle_off():
    params = AdmeParams(apply_adme_to_manual=False)
    out = filter_compounds([_manual_compound()], params)
    assert out["bypassed_count"] == 1 and out["failed_count"] == 0


def test_manual_filtered_when_toggle_on():
    # MW 900 violates default max → not bypassed, lands in failed.
    params = AdmeParams(apply_adme_to_manual=True)
    out = filter_compounds([_manual_compound()], params)
    assert out["bypassed_count"] == 0 and out["failed_count"] == 1


# ---------------------------------------------------------------------------
# Regression: stage2 run() output must include all expected ADME field names
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage2_output_includes_all_adme_fields():
    """stage2_adme.run() compound dicts must include all 7 ADME display fields.

    Regression guard: a prior bug omitted some field names from the enriched
    compound list, breaking the frontend Stage 2 table display.
    """
    from analysis.stages.stage2_adme import run as stage2_run
    from app.models.analysis import AnalysisRun

    compound_id = str(uuid4())

    # Fake AnalysisRun with stage_1 result pointing to our compound
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {}
    run.stage_results = {
        "stage_1": {
            "compound_ids": [compound_id],
            "compounds": [{"compound_id": compound_id, "plant_ids": ["pl_1"]}],
        }
    }

    # Fake DB compound with all ADME fields populated
    fake_db_compound = MagicMock()
    fake_db_compound.compound_id = compound_id
    fake_db_compound.canonical_name = "Test Compound"
    fake_db_compound.smiles = "CC(=O)O"
    fake_db_compound.chembl_id = None
    fake_db_compound.pubchem_cid = None
    fake_db_compound.molecular_weight = 300.0
    fake_db_compound.logp = 2.0
    fake_db_compound.hbond_donors = 1
    fake_db_compound.hbond_acceptors = 3
    fake_db_compound.tpsa = 60.0
    fake_db_compound.rotatable_bonds = 4
    fake_db_compound.np_likeness_score = 0.3
    fake_db_compound.is_pains_positive = False
    fake_db_compound.num_ro5_violations = 0

    session = AsyncMock()
    config = PipelineConfig()

    with patch(
        "analysis.stages.stage2_adme.compound_repo.get_compounds_by_ids",
        return_value=[fake_db_compound],
    ):
        result = await stage2_run(run, config, session)

    assert "compounds" in result, "stage2 output must have 'compounds' key"
    assert len(result["compounds"]) == 1

    compound_out = result["compounds"][0]

    expected_fields = [
        "molecular_weight",
        "logp",
        "tpsa",
        "hbond_donors",
        "hbond_acceptors",
        "np_likeness_score",
        "rotatable_bonds",
    ]
    for field in expected_fields:
        assert field in compound_out, (
            f"Stage 2 compound output missing expected ADME field: '{field}'. "
            f"Available keys: {list(compound_out.keys())}"
        )


@pytest.mark.asyncio
async def test_stage2_bypassed_manual_compound_status():
    """A bypassed manual compound reports status='bypassed', adme_pass=False, still active."""
    from analysis.stages.stage2_adme import run as stage2_run
    from app.models.analysis import AnalysisRun

    compound_id = str(uuid4())
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {"manual_compound_ids": [compound_id]}
    run.stage_results = {
        "stage_1": {
            "compound_ids": [compound_id],
            "compounds": [{"compound_id": compound_id, "plant_ids": []}],
        }
    }

    fake = MagicMock()
    fake.compound_id = compound_id
    fake.canonical_name = "User Mol"
    fake.smiles = None
    fake.chembl_id = None
    fake.pubchem_cid = None
    fake.molecular_weight = 900.0   # would fail Lipinski if screened
    fake.logp = 8.0
    fake.hbond_donors = 1
    fake.hbond_acceptors = 2
    fake.tpsa = 40.0
    fake.rotatable_bonds = 3
    fake.np_likeness_score = 0.1
    fake.is_pains_positive = False
    fake.num_ro5_violations = 2

    session = AsyncMock()
    config = PipelineConfig()
    # Reassign the whole adme config (don't mutate a field — AdmeParams may be frozen).
    config.adme = AdmeParams(apply_adme_to_manual=False)  # opt into bypass

    with patch(
        "analysis.stages.stage2_adme.compound_repo.get_compounds_by_ids",
        return_value=[fake],
    ):
        result = await stage2_run(run, config, session)

    out = result["compounds"][0]
    assert out["status"] == "bypassed"
    assert out["adme_pass"] is False
    assert out["adme_bypassed"] is True
    assert result["bypassed"] == 1
    assert result["passed"] == 0
    assert compound_id in result["all_active_compound_ids"]
