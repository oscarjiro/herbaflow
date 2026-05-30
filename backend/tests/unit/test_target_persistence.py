"""Tests for target DB caching after successful UniProt validation.

Symmetric to test_compound_persistence.py. Covers:
1. Validated target (has UniProt accession) -> persisted to targets table
2. Unvalidated target (skip_validation, uniprot_id=None) -> NOT persisted
3. Already-existing target (same target_id) -> upsert skips insert (no crash)
4. No CompoundTarget / DiseaseTarget link rows are created during caching
5. InjectTargetsResponse exposes a 'cached' count field (defaults to 0)
6. DB error during caching -> logs warning and returns 0 (does not raise)
7. inject-targets endpoint (validated path) wires caching and reports 'cached'
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID


# Validated targets as produced by inject_targets after UniProt validation.
VALIDATED_TARGETS = [
    {
        "target_id": "uniprot:P04637",
        "gene_symbol": "TP53",
        "uniprot_id": "P04637",
        "protein_name": "Cellular tumor antigen p53",
        "compound_ids": [],
        "sources": ["manual"],
    },
    {
        "target_id": "uniprot:P00533",
        "gene_symbol": "EGFR",
        "uniprot_id": "P00533",
        "protein_name": "Epidermal growth factor receptor",
        "compound_ids": [],
        "sources": ["manual"],
    },
]

# Unvalidated targets as produced by the skip_validation fast path — no accession.
UNVALIDATED_TARGETS = [
    {
        "target_id": "manual:AKT1",
        "gene_symbol": "AKT1",
        "uniprot_id": None,
        "protein_name": None,
        "compound_ids": [],
        "sources": ["manual_unvalidated"],
    }
]


@pytest.mark.asyncio
async def test_cache_validated_targets_persists_validated():
    """Targets with a UniProt accession are inserted into the targets table."""
    from app.services.target_cache import cache_validated_targets
    from app.models.target import Target

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None  # not yet in DB
    mock_session.exec.return_value = mock_result

    count = await cache_validated_targets(VALIDATED_TARGETS, mock_session)

    assert count == 2
    assert mock_session.add.call_count == 2
    for added_call in mock_session.add.call_args_list:
        obj = added_call.args[0]
        assert isinstance(obj, Target), f"Expected Target, got {type(obj)}"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cache_validated_targets_skips_unvalidated():
    """Targets without a UniProt accession (skip_validation) are not persisted."""
    from app.services.target_cache import cache_validated_targets

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None
    mock_session.exec.return_value = mock_result

    count = await cache_validated_targets(UNVALIDATED_TARGETS, mock_session)

    assert count == 0
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_cache_validated_targets_skips_existing():
    """If a target_id already exists in DB, it is not inserted again."""
    from app.services.target_cache import cache_validated_targets
    from app.models.target import Target

    mock_session = AsyncMock()
    existing = MagicMock(spec=Target)
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = existing
    mock_session.exec.return_value = mock_result

    count = await cache_validated_targets(VALIDATED_TARGETS, mock_session)

    assert count == 0
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_cache_validated_targets_no_link_rows():
    """Caching must never create CompoundTarget or DiseaseTarget association rows."""
    from app.services.target_cache import cache_validated_targets
    from app.models.target import CompoundTarget, DiseaseTarget

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None
    mock_session.exec.return_value = mock_result

    await cache_validated_targets(VALIDATED_TARGETS, mock_session)

    for added_call in mock_session.add.call_args_list:
        obj = added_call.args[0]
        assert not isinstance(obj, (CompoundTarget, DiseaseTarget)), \
            "Must NOT add link rows during caching"


def test_inject_targets_response_includes_cached_field():
    """InjectTargetsResponse must have a 'cached' integer field."""
    from app.schemas.analysis import InjectTargetsResponse

    resp = InjectTargetsResponse(
        injected=2,
        failed=[],
        duplicates_removed=0,
        duplicate_names=[],
        cached=2,
    )
    assert resp.cached == 2


def test_inject_targets_response_cached_defaults_to_zero():
    """'cached' defaults to 0 for backward compatibility when not provided."""
    from app.schemas.analysis import InjectTargetsResponse

    resp = InjectTargetsResponse(injected=1, failed=[])
    assert resp.cached == 0


@pytest.mark.asyncio
async def test_cache_validated_targets_db_error_returns_zero():
    """If the DB raises during caching, the function returns 0 (does not re-raise)."""
    from app.services.target_cache import cache_validated_targets

    mock_session = AsyncMock()
    mock_session.exec.side_effect = Exception("DB connection lost")

    count = await cache_validated_targets(VALIDATED_TARGETS, mock_session)
    assert count == 0


@pytest.mark.asyncio
async def test_inject_targets_endpoint_reports_cached():
    """inject_targets validated path calls the cache and surfaces its count."""
    from app.routers.analyses import inject_targets
    from app.schemas.analysis import InjectTargetsRequest

    ANALYSIS_UUID = UUID("00000000-0000-0000-0000-000000000044")
    run = MagicMock()
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    tp53 = MagicMock()
    tp53.gene_symbol = "TP53"
    tp53.uniprot_accession = "P04637"
    tp53.protein_name = "Cellular tumor antigen p53"

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.routers.analyses.validate_human_target", new=AsyncMock(return_value=tp53)), \
         patch("app.services.target_cache.cache_validated_targets", new=AsyncMock(return_value=1)) as mock_cache:

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53"])
        result = await inject_targets(ANALYSIS_UUID, request, mock_session)

    assert result.injected == 1
    assert result.cached == 1
    mock_cache.assert_awaited_once()


def test_inject_targets_response_has_normalized_and_unrecognized_fields():
    """InjectTargetsResponse exposes normalized[] and unrecognized[]; both default empty."""
    from app.schemas.analysis import InjectTargetsResponse

    resp = InjectTargetsResponse(injected=1, failed=[])
    assert resp.normalized == []
    assert resp.unrecognized == []

    resp2 = InjectTargetsResponse(
        injected=2,
        failed=[],
        normalized=[{"from": "TNFA", "to": "TNF"}],
        unrecognized=["ZZZ9"],
    )
    assert resp2.normalized == [{"from": "TNFA", "to": "TNF"}]
    assert resp2.unrecognized == ["ZZZ9"]


@pytest.mark.asyncio
async def test_inject_targets_lenient_normalizes_symbols():
    """Lenient mode resolves an alias to canonical HGNC and reports the change."""
    from app.routers.analyses import inject_targets
    from app.schemas.analysis import InjectTargetsRequest
    import app.services.gene_symbols as gs

    gs._MAP = {
        "TNFA": {"symbol": "TNF", "kind": "alias"},
        "TP53": {"symbol": "TP53", "kind": "approved"},
    }
    ANALYSIS_UUID = UUID("00000000-0000-0000-0000-000000000055")
    run = MagicMock()
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    captured = {}

    async def _capture_status(session, aid, status=None, stage_results=None):
        captured["stage3"] = stage_results["stage_3"]
        return run

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(side_effect=_capture_status)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.target_cache.cache_validated_targets", new=AsyncMock(return_value=0)):
        request = InjectTargetsRequest(targets=["TNFA", "TP53"], skip_validation=True)
        result = await inject_targets(ANALYSIS_UUID, request, AsyncMock())

    assert result.injected == 2
    assert {"from": "TNFA", "to": "TNF"} in result.normalized
    symbols = captured["stage3"]["target_gene_symbols"]
    assert "TNF" in symbols and "TP53" in symbols
    assert "TNFA" not in symbols  # alias was canonicalized
    gs._MAP = None


@pytest.mark.asyncio
async def test_inject_targets_lenient_dedups_alias_and_canonical():
    """Submitting an alias and its canonical collapses to one target after normalization."""
    from app.routers.analyses import inject_targets
    from app.schemas.analysis import InjectTargetsRequest
    import app.services.gene_symbols as gs

    gs._MAP = {"TNFA": {"symbol": "TNF", "kind": "alias"}, "TNF": {"symbol": "TNF", "kind": "approved"}}
    run = MagicMock()
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.target_cache.cache_validated_targets", new=AsyncMock(return_value=0)):
        request = InjectTargetsRequest(targets=["TNF", "TNFA"], skip_validation=True)
        result = await inject_targets(UUID("00000000-0000-0000-0000-000000000056"), request, AsyncMock())

    assert result.injected == 1
    assert result.duplicates_removed == 1
    gs._MAP = None


@pytest.mark.asyncio
async def test_inject_targets_lenient_unknown_kept_and_flagged():
    """An unknown symbol is kept (injected) but reported in unrecognized[]."""
    from app.routers.analyses import inject_targets
    from app.schemas.analysis import InjectTargetsRequest
    import app.services.gene_symbols as gs

    gs._MAP = {"TP53": {"symbol": "TP53", "kind": "approved"}}
    run = MagicMock()
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.target_cache.cache_validated_targets", new=AsyncMock(return_value=0)):
        request = InjectTargetsRequest(targets=["ZZZ9"], skip_validation=True)
        result = await inject_targets(UUID("00000000-0000-0000-0000-000000000057"), request, AsyncMock())

    assert result.injected == 1
    assert result.unrecognized == ["ZZZ9"]
    gs._MAP = None


@pytest.mark.asyncio
async def test_inject_targets_lenient_accession_routes_to_uniprot():
    """A UniProt accession in lenient mode is resolved via UniProt, not the offline map."""
    from app.routers.analyses import inject_targets
    from app.schemas.analysis import InjectTargetsRequest
    import app.services.gene_symbols as gs

    gs._MAP = {}
    info = MagicMock()
    info.gene_symbol = "TP53"
    info.uniprot_accession = "P04637"
    info.protein_name = "Cellular tumor antigen p53"

    run = MagicMock()
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.routers.analyses.validate_human_target", new=AsyncMock(return_value=info)) as mock_val, \
         patch("app.services.target_cache.cache_validated_targets", new=AsyncMock(return_value=1)):
        request = InjectTargetsRequest(targets=["P04637"], skip_validation=True)
        result = await inject_targets(UUID("00000000-0000-0000-0000-000000000058"), request, AsyncMock())

    mock_val.assert_awaited_once()
    assert result.injected == 1
    gs._MAP = None


@pytest.mark.asyncio
async def test_inject_targets_lenient_accession_uniprot_down_kept_no_503():
    """If UniProt is unavailable for an accession in lenient mode, keep+flag (no 503)."""
    from app.routers.analyses import inject_targets
    from app.schemas.analysis import InjectTargetsRequest
    from integrations._retry import ServiceUnavailableError
    import app.services.gene_symbols as gs

    gs._MAP = {}
    run = MagicMock()
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.routers.analyses.validate_human_target", new=AsyncMock(side_effect=ServiceUnavailableError("down"))), \
         patch("app.services.target_cache.cache_validated_targets", new=AsyncMock(return_value=0)):
        request = InjectTargetsRequest(targets=["P04637"], skip_validation=True)
        result = await inject_targets(UUID("00000000-0000-0000-0000-000000000059"), request, AsyncMock())

    assert result.injected == 1
    assert "P04637" in result.unrecognized
    gs._MAP = None
