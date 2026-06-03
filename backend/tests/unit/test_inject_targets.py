"""Unit tests for manual-target injection logic (inject_targets_service).

Tests:
1. Valid gene symbol → injected with gene_symbol, uniprot_id, protein_name
2. Valid UniProt accession → injected directly
3. Unknown gene symbol → in failed list
4. Input mode set to manual_targets in parameters
5. Empty targets list → 422 (Pydantic ValidationError)
6. Deduplication: same gene symbol appears twice → only one entry injected
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from app.services.manual_inputs import inject_targets_service

ANALYSIS_ID = "00000000-0000-0000-0000-000000000044"
ANALYSIS_UUID = UUID(ANALYSIS_ID)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(status: str = "pending") -> MagicMock:
    run = MagicMock()
    run.analysis_id = ANALYSIS_UUID
    run.status = status
    run.parameters = {}
    run.stage_results = {}
    return run


def _make_uniprot_target(gene: str, accession: str, protein_name: str | None = None):
    """Return a mock UniProtTarget dataclass-like object."""
    t = MagicMock()
    t.gene_symbol = gene
    t.uniprot_accession = accession
    t.protein_name = protein_name
    return t


# ---------------------------------------------------------------------------
# Test 1: Valid gene symbol → injected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_valid_gene_symbol():
    run = _make_run(status="pending")
    captured_stage_results = {}
    captured_params = {}

    async def fake_update(session, analysis_id, status, **kwargs):
        if "stage_results" in kwargs:
            captured_stage_results.update(kwargs["stage_results"])
        return run

    async def fake_merge(session, analysis_id, params):
        captured_params.update(params)

    tp53_target = _make_uniprot_target("TP53", "P04637", "Cellular tumor antigen p53")

    with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(side_effect=fake_update)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock(side_effect=fake_merge)), \
         patch("app.services.manual_inputs.validate_human_target", new=AsyncMock(return_value=tp53_target)):

        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53"])
        result = await inject_targets_service(request.targets, request.skip_validation, run, mock_session)

    assert result.injected == 1
    assert result.failed == []
    assert "stage_3" in captured_stage_results
    stage3 = captured_stage_results["stage_3"]
    assert len(stage3["targets"]) == 1
    t = stage3["targets"][0]
    assert t["gene_symbol"] == "TP53"
    assert t["uniprot_id"] == "P04637"
    assert t["protein_name"] == "Cellular tumor antigen p53"
    assert t["sources"] == ["manual"]
    assert t["compound_ids"] == []
    assert "target_score" not in t


# ---------------------------------------------------------------------------
# Test 2: Valid UniProt accession → injected directly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_valid_uniprot_accession():
    run = _make_run(status="pending")
    captured_stage_results = {}

    async def fake_update(session, analysis_id, status, **kwargs):
        if "stage_results" in kwargs:
            captured_stage_results.update(kwargs["stage_results"])
        return run

    egfr_target = _make_uniprot_target("EGFR", "P00533", "Epidermal growth factor receptor")

    with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(side_effect=fake_update)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.manual_inputs.validate_human_target", new=AsyncMock(return_value=egfr_target)) as mock_validate:

        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["P00533"])
        result = await inject_targets_service(request.targets, request.skip_validation, run, mock_session)

    assert result.injected == 1
    assert result.failed == []
    # When input looks like a UniProt accession, validate_human_target called with
    # uniprot_id=..., gene_symbol=None
    call_kwargs = mock_validate.call_args.kwargs
    assert call_kwargs.get("uniprot_id") == "P00533"
    assert call_kwargs.get("gene_symbol") is None


# ---------------------------------------------------------------------------
# Test 3: Unknown gene symbol → in failed list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_unknown_gene_symbol_in_failed():
    run = _make_run(status="pending")

    async def fake_validate(gene_symbol=None, uniprot_id=None):
        if gene_symbol == "FAKEGENE":
            raise ValueError("Gene symbol 'FAKEGENE' not found as human protein in UniProt")
        # TP53 succeeds
        return _make_uniprot_target("TP53", "P04637")

    with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.manual_inputs.validate_human_target", new=AsyncMock(side_effect=fake_validate)):

        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53", "FAKEGENE"])
        result = await inject_targets_service(request.targets, request.skip_validation, run, mock_session)

    assert result.injected == 1
    assert "FAKEGENE" in result.failed


# ---------------------------------------------------------------------------
# Test 4: Input mode set to manual_targets in parameters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_targets_sets_input_mode():
    run = _make_run(status="pending")
    captured_params = {}

    async def fake_merge(session, analysis_id, params):
        captured_params.update(params)

    tp53_target = _make_uniprot_target("TP53", "P04637")

    with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock(side_effect=fake_merge)), \
         patch("app.services.manual_inputs.validate_human_target", new=AsyncMock(return_value=tp53_target)):

        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53"])
        await inject_targets_service(request.targets, request.skip_validation, run, mock_session)

    assert captured_params.get("_input_mode") == "manual_targets"


# ---------------------------------------------------------------------------
# Test 5: Empty targets list → 422
# ---------------------------------------------------------------------------

def test_inject_targets_empty_list_422():
    """Empty targets list must be rejected.

    Previously the router enforced this via an explicit HTTPException.
    Now InjectTargetsRequest has min_length=1 on the ``targets`` field,
    so Pydantic raises ValidationError *before* the route handler runs.
    FastAPI converts this to a 422 Unprocessable Entity automatically.
    """
    from pydantic import ValidationError
    from app.schemas.analysis import InjectTargetsRequest

    with pytest.raises(ValidationError) as exc_info:
        InjectTargetsRequest(targets=[])

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("targets",) for e in errors)


# ---------------------------------------------------------------------------
# Test 6: Deduplication — same gene injected twice produces one entry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_targets_deduplicates_gene_symbols():
    run = _make_run(status="pending")
    captured_stage_results = {}

    async def fake_update(session, analysis_id, status, **kwargs):
        if "stage_results" in kwargs:
            captured_stage_results.update(kwargs["stage_results"])
        return run

    tp53_target = _make_uniprot_target("TP53", "P04637")

    with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(side_effect=fake_update)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.manual_inputs.validate_human_target", new=AsyncMock(return_value=tp53_target)):

        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        # TP53 submitted twice
        request = InjectTargetsRequest(targets=["TP53", "TP53"])
        result = await inject_targets_service(request.targets, request.skip_validation, run, mock_session)

    assert result.injected == 1
    stage3 = captured_stage_results["stage_3"]
    assert len(stage3["targets"]) == 1
    assert stage3["target_count"] == 1


# ---------------------------------------------------------------------------
# Test 7: Regression — lean stage-4 rows (no per-row disease_name) must not crash
# ---------------------------------------------------------------------------


def test_add_target_to_stage4_with_lean_rows_no_disease_name():
    """Injecting into a single-disease (lean) stage-4 result must not require per-row disease_name."""
    from app.routers.analyses import _add_target_to_stage4
    stage4 = {
        "disease_id": "dis_1",
        "disease_name": "Type 2 Diabetes",
        "disease_target_count": 1,
        "disease_gene_symbols": ["AKT1"],
        "targets": [
            {"gene_symbol": "AKT1", "uniprot_accession": "P31749", "score": 0.7, "source": "db_cache"},
        ],
    }
    updated = _add_target_to_stage4(stage4, "TP53", "P04637", "Cellular tumor antigen p53")
    new_row = next(t for t in updated["targets"] if t["gene_symbol"] == "TP53")
    assert "disease_name" not in new_row
    assert new_row["source"] == "user_provided"
    assert updated["disease_target_count"] == 2
    assert "TP53" in updated["disease_gene_symbols"]
