"""Unit tests for inject-compounds request validation, user-compound add/remove
endpoints, and the compound deduplication service.

Tests:
1. Empty compounds list → Pydantic ValidationError (min_length=1)
2. Compounds list exceeding HARD_CAP_MANUAL_COMPOUNDS items → Pydantic ValidationError
3. POST /analyses/{id}/user-compounds adds a compound to stage_1 results
4. DELETE /analyses/{id}/user-compounds/{compound_id} removes a compound from stage_1
"""
import httpx
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.analysis import InjectCompoundsRequest, HARD_CAP_MANUAL_COMPOUNDS

ANALYSIS_ID = "00000000-0000-0000-0000-000000000043"


# ---------------------------------------------------------------------------
# Test 1: Empty compounds list → ValidationError
# ---------------------------------------------------------------------------


def test_inject_compounds_empty_list_raises_validation_error():
    """InjectCompoundsRequest(compounds=[]) must raise a Pydantic ValidationError.

    The ``compounds`` field has min_length=1, so an empty list is rejected
    before the route handler runs.
    """
    with pytest.raises(ValidationError) as exc_info:
        InjectCompoundsRequest(compounds=[])

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("compounds",) for e in errors)


# ---------------------------------------------------------------------------
# Test 2: Over-limit compounds list → ValidationError
# ---------------------------------------------------------------------------


def test_inject_compounds_over_limit_raises_validation_error():
    """InjectCompoundsRequest with > HARD_CAP_MANUAL_COMPOUNDS items must raise a Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        InjectCompoundsRequest(compounds=["CC"] * (HARD_CAP_MANUAL_COMPOUNDS + 1))

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("compounds",) for e in errors)


# ---------------------------------------------------------------------------
# Test 3: POST /analyses/{id}/user-compounds adds a compound to stage_1
# ---------------------------------------------------------------------------

_ASPIRIN_SMILES = "CC(=O)Oc1ccccc1C(=O)O"
_MOCK_COMPOUND = {
    "compound_id": "11111111-1111-1111-1111-111111111111",
    "canonical_name": "aspirin",
    "inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
    "iupac_name": "2-(acetyloxy)benzoic acid",
    "molecular_formula": "C9H8O4",
    "molecular_weight": 180.16,
    "smiles": _ASPIRIN_SMILES,
    "logp": 1.2,
    "tpsa": 63.6,
    "hbond_donors": 1,
    "hbond_acceptors": 4,
    "rotatable_bonds": 3,
    "np_likeness_score": None,
    "lipinski_pass": True,
    "adme_pass": True,
    "is_pains_positive": False,
    "is_np_exception": False,
    "plant_ids": [],
}

_STAGE1_WITH_COMPOUND = {
    "compound_ids": ["11111111-1111-1111-1111-111111111111"],
    "compound_count": 1,
    "plant_ids": [],
    "total_compounds": 1,
    "plants_covered": 0,
    "compounds": [
        {
            "compound_id": "11111111-1111-1111-1111-111111111111",
            "canonical_name": "aspirin",
            "plant_ids": [],
        }
    ],
    "user_modified": True,
}


def _make_mock_run(stage1: dict | None = None):
    """Build a minimal mock AnalysisRun for unit tests."""
    run = MagicMock()
    run.stage_results = {"stage_1": stage1} if stage1 else {}
    run.status = "stage_1_awaiting_approval"
    return run


_STAGE1_EMPTY = {
    "compound_ids": [],
    "compound_count": 0,
    "plant_ids": [],
    "total_compounds": 0,
    "plants_covered": 0,
    "compounds": [],
}


def test_add_user_compound_to_stage1():
    """POST /analyses/{id}/user-compounds adds a compound to stage_1 results.

    The endpoint requires stage_1 results to exist before compounds can be added,
    so we supply a minimal (empty) stage_1 in the mock run. The endpoint validates
    via PubChem first (no lock held), guards existence via the unlocked ``get_run``,
    then commits the stage_1 merge through ``merge_stage_results_locked`` in one
    locked transaction — so we patch those two repo calls.
    """
    mock_run = _make_mock_run(stage1=_STAGE1_EMPTY)

    async def _fake_merge(session, analysis_id, mutate, status=None):
        # Mirror the real primitive: apply the mutate closure to the CURRENT
        # stage_results under the lock, then return the run.
        mock_run.stage_results = mutate(dict(mock_run.stage_results or {}))
        return mock_run

    with (
        patch("app.repositories.analysis_repo.get_run", new=AsyncMock(return_value=mock_run)),
        patch("app.repositories.analysis_repo.merge_stage_results_locked", new=AsyncMock(side_effect=_fake_merge)),
        patch(
            "integrations.pubchem_compound.validate_compound",
            new=AsyncMock(return_value=_MOCK_COMPOUND),
        ),
        patch("app.database.get_session"),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            f"/analyses/{ANALYSIS_ID}/user-compounds",
            json={"smiles": _ASPIRIN_SMILES},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["compound_id"] is not None
    assert data["canonical_name"] == "aspirin"


# ---------------------------------------------------------------------------
# Test 5: DELETE /analyses/{id}/user-compounds/{compound_id} removes it
# ---------------------------------------------------------------------------


def test_remove_user_compound_from_stage1():
    """DELETE /analyses/{id}/user-compounds/{compound_id} removes the compound."""
    mock_run = _make_mock_run(stage1=_STAGE1_WITH_COMPOUND)

    with (
        patch("app.repositories.analysis_repo.get_run_locked", new=AsyncMock(return_value=mock_run)),
        patch("app.repositories.analysis_repo.update_run_status", new=AsyncMock()),
        patch("app.database.get_session"),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.delete(
            f"/analyses/{ANALYSIS_ID}/user-compounds/11111111-1111-1111-1111-111111111111",
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["removed"] == "11111111-1111-1111-1111-111111111111"


# ---------------------------------------------------------------------------
# Deduplication service unit tests
# ---------------------------------------------------------------------------


class TestDeduplicateCompoundsService:
    """Tests for app.services.compound_dedup.deduplicate_compounds()."""

    @pytest.mark.asyncio
    async def test_same_cid_submitted_twice_keeps_one(self):
        """Two inputs resolving to the same compound_id → only one in unique_new."""
        compound = {
            "compound_id": "cid-aaa",
            "inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            "canonical_name": "aspirin",
        }

        async def mock_validate(structure, client):
            return dict(compound)

        with patch(
            "app.services.compound_dedup.validate_compound",
            side_effect=mock_validate,
        ):
            from app.services.compound_dedup import deduplicate_compounds
            unique_new, duplicates = await deduplicate_compounds(
                submitted=["CC(=O)Oc1ccccc1C(=O)O", "aspirin smiles variant"],
                existing_ids=set(),
                client=MagicMock(),
            )

        assert len(unique_new) == 1
        assert len(duplicates) == 1

    @pytest.mark.asyncio
    async def test_compound_already_in_analysis_excluded(self):
        """Compound whose compound_id is in existing_ids → in duplicates, not unique_new."""
        compound = {
            "compound_id": "cid-existing",
            "inchikey": "EXISTING-INCHIKEY",
            "canonical_name": "quercetin",
        }

        async def mock_validate(structure, client):
            return dict(compound)

        with patch(
            "app.services.compound_dedup.validate_compound",
            side_effect=mock_validate,
        ):
            from app.services.compound_dedup import deduplicate_compounds
            unique_new, duplicates = await deduplicate_compounds(
                submitted=["OC1=CC=C(C=C1)O"],
                existing_ids={"cid-existing"},
                client=MagicMock(),
            )

        assert len(unique_new) == 0
        assert len(duplicates) == 1

    @pytest.mark.asyncio
    async def test_different_formats_same_cid_deduped(self):
        """SMILES and a second input both resolving to same CID → only one kept."""
        compound = {
            "compound_id": "cid-bbb",
            "inchikey": "RYYVLZVUVIJVGH-UHFFFAOYSA-N",
            "canonical_name": "caffeine",
        }

        async def mock_validate(structure, client):
            return dict(compound)

        with patch(
            "app.services.compound_dedup.validate_compound",
            side_effect=mock_validate,
        ):
            from app.services.compound_dedup import deduplicate_compounds
            unique_new, duplicates = await deduplicate_compounds(
                submitted=[
                    "Cn1cnc2c1c(=O)n(C)c(=O)n2C",  # SMILES
                    "RYYVLZVUVIJVGH-UHFFFAOYSA-N",   # InChIKey (same compound)
                ],
                existing_ids=set(),
                client=MagicMock(),
            )

        assert len(unique_new) == 1
        assert len(duplicates) == 1

    @pytest.mark.asyncio
    async def test_response_always_contains_dedup_keys(self):
        """InjectCompoundsResponse always exposes injected/duplicates_removed/duplicate_names."""
        from app.schemas.analysis import InjectCompoundsResponse

        resp = InjectCompoundsResponse(
            injected=3,
            failed=[],
            duplicates_removed=2,
            duplicate_names=["aspirin", "quercetin"],
        )
        assert resp.injected == 3
        assert resp.duplicates_removed == 2
        assert resp.duplicate_names == ["aspirin", "quercetin"]

    @pytest.mark.asyncio
    async def test_pubchem_unavailable_falls_back_to_string_dedup(self):
        """PubChem returning None → string-based fallback dedup (lowercased, stripped)."""
        async def mock_validate_unavailable(structure, client):
            return None

        with patch(
            "app.services.compound_dedup.validate_compound",
            side_effect=mock_validate_unavailable,
        ):
            from app.services.compound_dedup import deduplicate_compounds
            unique_new, duplicates = await deduplicate_compounds(
                submitted=["Aspirin", "ASPIRIN", "  aspirin  "],
                existing_ids=set(),
                client=MagicMock(),
            )

        # All three normalize to "aspirin" — keep one
        assert len(unique_new) == 1
        assert len(duplicates) == 2

    @pytest.mark.asyncio
    async def test_timeout_exception_degrades_gracefully(self):
        """validate_compound raising httpx.TimeoutException → dedup falls back to string key.

        The dedup service must not crash when PubChem times out. Instead it catches
        the exception, logs a warning, and falls back to lowercased string comparison
        for the affected compound — keeping the batch alive.
        """
        async def mock_validate_timeout(structure, client):
            raise httpx.TimeoutException("connect timeout")

        with patch(
            "app.services.compound_dedup.validate_compound",
            side_effect=mock_validate_timeout,
        ):
            from app.services.compound_dedup import deduplicate_compounds
            # Two distinct inputs — both fail PubChem, fall back to string keys
            unique_new, duplicates = await deduplicate_compounds(
                submitted=["aspirin", "quercetin"],
                existing_ids=set(),
                client=MagicMock(),
            )

        # Both are kept (different string keys), no crash
        assert unique_new == ["aspirin", "quercetin"]
        assert duplicates == []

    @pytest.mark.asyncio
    async def test_timeout_exception_with_duplicate_degrades_gracefully(self):
        """TimeoutException + duplicate string → dedup still removes the duplicate.

        Even when PubChem is down and string fallback is active, within-batch
        dedup must still work correctly for repeated raw inputs.
        """
        async def mock_validate_timeout(structure, client):
            raise httpx.TimeoutException("connect timeout")

        with patch(
            "app.services.compound_dedup.validate_compound",
            side_effect=mock_validate_timeout,
        ):
            from app.services.compound_dedup import deduplicate_compounds
            unique_new, duplicates = await deduplicate_compounds(
                submitted=["aspirin", "ASPIRIN", "  aspirin  "],
                existing_ids=set(),
                client=MagicMock(),
            )

        # All three normalize to "aspirin" under string fallback — keep one
        assert len(unique_new) == 1
        assert len(duplicates) == 2
