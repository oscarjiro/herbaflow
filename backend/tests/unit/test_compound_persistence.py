"""Tests for compound DB caching after successful canonicalization.

Covers:
1. Successfully canonicalized compound (has PubChem CID) → persisted to DB
2. Canonicalization-failed but SMILES-valid compound → NOT persisted
3. Already-existing compound (same compound_id) → upsert skips insert (no crash)
4. No plant-compound link created during caching
5. inject_compounds response includes 'cached' count
6. DB error during caching → logs warning and proceeds (does not fail endpoint)
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures: shared test data
# ---------------------------------------------------------------------------

VALIDATED_WITH_CID = [
    {
        "compound_id": "aaaa0000-0000-0000-0000-000000000001",
        "canonical_name": "aspirin",
        "canonical_key": "pubchem:2244",
        "pubchem_cid": "2244",
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        "molecular_weight": 180.16,
        "logp": 1.2,
        "tpsa": 63.6,
        "hbond_donors": 1,
        "hbond_acceptors": 4,
        "rotatable_bonds": 3,
        "np_likeness_score": None,
        "adme_pass": True,
        "is_pains_positive": False,
        "is_np_exception": False,
    },
    {
        "compound_id": "bbbb0000-0000-0000-0000-000000000002",
        "canonical_name": "quercetin",
        "canonical_key": "pubchem:5280343",
        "pubchem_cid": "5280343",
        "smiles": "O=c1c(O)c(-c2ccc(O)c(O)c2)oc2cc(O)cc(O)c12",
        "inchikey": "REFJWTPEDVJJIY-UHFFFAOYSA-N",
        "molecular_weight": 302.24,
        "logp": 1.54,
        "tpsa": 131.4,
        "hbond_donors": 5,
        "hbond_acceptors": 7,
        "rotatable_bonds": 1,
        "np_likeness_score": 1.2,
        "adme_pass": False,
        "is_pains_positive": False,
        "is_np_exception": True,
    },
]

# Compound where PubChem CID lookup failed — pubchem_cid is None
VALIDATED_NO_CID = [
    {
        "compound_id": "cccc0000-0000-0000-0000-000000000003",
        "canonical_name": "user_provided",
        "canonical_key": "smiles:CC(O)=O",
        "pubchem_cid": None,
        "smiles": "CC(O)=O",
        "inchikey": None,
        "molecular_weight": 60.05,
        "logp": -0.17,
        "tpsa": 37.3,
        "hbond_donors": 1,
        "hbond_acceptors": 2,
        "rotatable_bonds": 1,
        "np_likeness_score": None,
        "adme_pass": True,
        "is_pains_positive": False,
        "is_np_exception": False,
    }
]


# ---------------------------------------------------------------------------
# Test 1: Compounds with valid CIDs are persisted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_validated_compounds_persists_cid_compounds():
    """Compounds with a pubchem_cid are inserted into the compounds table."""
    from app.models.compound import Compound
    from app.services.compound_persist import persist_validated_compounds

    mock_session = AsyncMock()
    # exec returns empty result → compound not yet in DB → we insert
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec.return_value = mock_result

    count = await persist_validated_compounds(VALIDATED_WITH_CID, mock_session)

    assert count == 2
    # session.add should be called once per new compound
    assert mock_session.add.call_count == 2
    # Each added object should be a Compound (not PlantCompound or anything else)
    for added_call in mock_session.add.call_args_list:
        obj = added_call.args[0]
        assert isinstance(obj, Compound), f"Expected Compound, got {type(obj)}"
    # commit should be called
    mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: Compounds without CID are NOT persisted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_validated_compounds_skips_no_cid():
    """Compounds with pubchem_cid=None are not inserted — they are user_provided/unvalidated."""
    from app.services.compound_persist import persist_validated_compounds

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec.return_value = mock_result

    count = await persist_validated_compounds(VALIDATED_NO_CID, mock_session)

    assert count == 0
    mock_session.add.assert_not_called()
    # commit is still safe to call even with nothing inserted
    # (implementation may or may not commit when count=0 — both are valid)


# ---------------------------------------------------------------------------
# Test 3: Already-existing compound is skipped (upsert / ON CONFLICT DO NOTHING)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_validated_compounds_skips_existing():
    """If a compound_id already exists in DB, it is not inserted again."""
    from app.models.compound import Compound
    from app.services.compound_persist import persist_validated_compounds

    mock_session = AsyncMock()
    # exec returns an existing Compound → do not insert
    existing = MagicMock(spec=Compound)
    mock_result = MagicMock()
    mock_result.first.return_value = existing
    mock_session.exec.return_value = mock_result

    count = await persist_validated_compounds(VALIDATED_WITH_CID, mock_session)

    assert count == 0
    mock_session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: No PlantCompound rows are created
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_validated_compounds_no_plant_links():
    """Caching must never create PlantCompound associations."""
    from app.models.compound import PlantCompound
    from app.services.compound_persist import persist_validated_compounds

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec.return_value = mock_result

    await persist_validated_compounds(VALIDATED_WITH_CID, mock_session)

    for added_call in mock_session.add.call_args_list:
        obj = added_call.args[0]
        assert not isinstance(obj, PlantCompound), "Must NOT add PlantCompound rows during caching"


# ---------------------------------------------------------------------------
# Test 5: inject_compounds response includes 'cached' count
# ---------------------------------------------------------------------------


def test_inject_compounds_response_includes_cached_count():
    """InjectCompoundsResponse must have a 'cached' integer field."""
    from app.schemas.analysis import InjectCompoundsResponse

    resp = InjectCompoundsResponse(
        injected=2,
        failed=[],
        duplicates_removed=0,
        duplicate_names=[],
        cached=2,
    )
    assert resp.cached == 2


def test_inject_compounds_response_cached_defaults_to_zero():
    """'cached' defaults to 0 for backward compatibility when not provided."""
    from app.schemas.analysis import InjectCompoundsResponse

    resp = InjectCompoundsResponse(
        injected=1,
        failed=[],
    )
    assert resp.cached == 0


# ---------------------------------------------------------------------------
# Test 6: DB error during caching → warning logged, endpoint proceeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_validated_compounds_db_error_returns_zero():
    """If the DB raises an exception during caching, the function returns 0 (not re-raises)."""
    from app.services.compound_persist import persist_validated_compounds

    mock_session = AsyncMock()
    mock_session.exec.side_effect = Exception("DB connection lost")

    # Must not raise — must return 0 (soft failure)
    count = await persist_validated_compounds(VALIDATED_WITH_CID, mock_session)
    assert count == 0


# ---------------------------------------------------------------------------
# Test 7: inject_compounds_service wires caching and surfaces the cached count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inject_compounds_service_reports_cached():
    """inject_compounds_service surfaces the persistence cache count in its response."""
    from uuid import UUID

    from app.schemas.analysis import InjectCompoundsRequest
    from app.services.manual_inputs import inject_compounds_service

    mock_run = MagicMock()
    mock_run.analysis_id = UUID("00000000-0000-0000-0000-000000000099")
    mock_run.status = "pending"
    mock_run.stage_results = {}
    mock_run.parameters = {}

    mock_validated = [
        {
            "compound_id": "aaaa0000-0000-0000-0000-000000000001",
            "canonical_name": "aspirin",
            "canonical_key": "pubchem:2244",
            "pubchem_cid": "2244",
            "smiles": "CC(=O)Oc1ccccc1C(=O)O",
            "inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            "molecular_weight": 180.16,
            "logp": 1.2,
            "tpsa": 63.6,
            "hbond_donors": 1,
            "hbond_acceptors": 4,
            "rotatable_bonds": 3,
            "np_likeness_score": None,
            "adme_pass": True,
            "is_pains_positive": False,
            "is_np_exception": False,
        }
    ]

    with (
        patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock()),
        patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()),
        patch(
            "app.services.manual_inputs.validate_compounds_batch",
            new=AsyncMock(return_value=(mock_validated, [])),
        ),
        patch(
            "app.services.manual_inputs.deduplicate_compounds",
            new=AsyncMock(return_value=(["CC(=O)Oc1ccccc1C(=O)O"], [])),
        ),
        patch(
            "app.services.compound_persist.persist_validated_compounds",
            new=AsyncMock(return_value=1),
        ),
    ):
        mock_session = AsyncMock()
        request = InjectCompoundsRequest(compounds=["CC(=O)Oc1ccccc1C(=O)O"])
        result = await inject_compounds_service(request.compounds, mock_run, mock_session)

    assert result.cached == 1
    assert result.injected == 1
