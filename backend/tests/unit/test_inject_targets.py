"""Unit tests for T4.4 — inject-targets endpoint.

Tests:
1. Valid gene symbol → injected with gene_symbol, uniprot_id, protein_name
2. Valid UniProt accession → injected directly
3. Unknown gene symbol → in failed list
4. Race condition guard: 409 when analysis status is not pending/failed
5. Input mode set to manual_targets in parameters
6. Empty targets list → 422 (Pydantic ValidationError)
7. Deduplication: same gene symbol appears twice → only one entry injected
8. HTTP boundary: POST /analyses/{id}/inject-targets with [] → HTTP 422
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from fastapi.testclient import TestClient
from app.main import app

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

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(side_effect=fake_update)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock(side_effect=fake_merge)), \
         patch("app.routers.analyses.validate_human_target", new=AsyncMock(return_value=tp53_target)):

        from app.routers.analyses import inject_targets
        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53"])
        result = await inject_targets(ANALYSIS_UUID, request, mock_session)

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

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(side_effect=fake_update)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.routers.analyses.validate_human_target", new=AsyncMock(return_value=egfr_target)) as mock_validate:

        from app.routers.analyses import inject_targets
        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["P00533"])
        result = await inject_targets(ANALYSIS_UUID, request, mock_session)

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

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.routers.analyses.validate_human_target", new=AsyncMock(side_effect=fake_validate)):

        from app.routers.analyses import inject_targets
        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53", "FAKEGENE"])
        result = await inject_targets(ANALYSIS_UUID, request, mock_session)

    assert result.injected == 1
    assert "FAKEGENE" in result.failed


# ---------------------------------------------------------------------------
# Test 4: Race condition guard — 409 when analysis is running/complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_targets_409_when_running():
    run = _make_run(status="stage_1_running")

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)):
        from app.routers.analyses import inject_targets
        from app.schemas.analysis import InjectTargetsRequest
        from fastapi import HTTPException

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53"])
        with pytest.raises(HTTPException) as exc_info:
            await inject_targets(ANALYSIS_UUID, request, mock_session)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_inject_targets_409_when_complete():
    run = _make_run(status="complete")

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)):
        from app.routers.analyses import inject_targets
        from app.schemas.analysis import InjectTargetsRequest
        from fastapi import HTTPException

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53"])
        with pytest.raises(HTTPException) as exc_info:
            await inject_targets(ANALYSIS_UUID, request, mock_session)

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Test 5: Input mode set to manual_targets in parameters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_targets_sets_input_mode():
    run = _make_run(status="pending")
    captured_params = {}

    async def fake_merge(session, analysis_id, params):
        captured_params.update(params)

    tp53_target = _make_uniprot_target("TP53", "P04637")

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock(side_effect=fake_merge)), \
         patch("app.routers.analyses.validate_human_target", new=AsyncMock(return_value=tp53_target)):

        from app.routers.analyses import inject_targets
        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53"])
        await inject_targets(ANALYSIS_UUID, request, mock_session)

    assert captured_params.get("_input_mode") == "manual_targets"


# ---------------------------------------------------------------------------
# Test 6: Empty targets list → 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_targets_empty_list_422():
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
# Test 7: Deduplication — same gene injected twice produces one entry
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

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(side_effect=fake_update)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.routers.analyses.validate_human_target", new=AsyncMock(return_value=tp53_target)):

        from app.routers.analyses import inject_targets
        from app.schemas.analysis import InjectTargetsRequest

        mock_session = AsyncMock()
        # TP53 submitted twice
        request = InjectTargetsRequest(targets=["TP53", "TP53"])
        result = await inject_targets(ANALYSIS_UUID, request, mock_session)

    assert result.injected == 1
    stage3 = captured_stage_results["stage_3"]
    assert len(stage3["targets"]) == 1
    assert stage3["target_count"] == 1


# ---------------------------------------------------------------------------
# Test 8: HTTP boundary — FastAPI translates Pydantic ValidationError → 422
# ---------------------------------------------------------------------------


def test_inject_targets_http_empty_list_returns_422():
    """Sending targets=[] over HTTP must produce a 422 response.

    This confirms the full FastAPI request/response boundary: Pydantic's
    ValidationError (raised because InjectTargetsRequest.targets has
    min_length=1) is automatically converted to HTTP 422 by FastAPI before
    the route handler is ever called.
    """
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/analyses/{ANALYSIS_ID}/inject-targets",
        json={"targets": []},
    )
    assert response.status_code == 422
