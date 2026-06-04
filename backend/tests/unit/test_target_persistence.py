"""Tests for target DB persistence after successful UniProt validation.

Symmetric to test_compound_persistence.py. Covers:
1. Validated target (has UniProt accession) -> persisted to targets table
2. Unvalidated target (skip_validation, uniprot_id=None) -> NOT persisted
3. Already-existing target (same target_id) -> upsert skips insert (no crash)
4. No CompoundTarget / DiseaseTarget link rows are created during persistence
5. InjectTargetsResponse exposes a 'cached' count field (defaults to 0)
6. DB error during persistence -> logs warning and returns 0 (does not raise)
7. inject-targets endpoint (validated path) wires persistence and reports 'cached'
8. persist_canonical_target primitive: insert-if-absent, no links, no commit
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

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


class _ExecResult:
    """Mimics ``await session.exec(stmt)`` — exposes ``.first()``."""

    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    """Async session stub for resolve_targets: every DB-first lookup is a miss.

    inject_targets_service now delegates to the unified resolve_targets, which issues
    one ``session.exec`` per novel input. Returning None makes every lookup a DB miss,
    forcing the UniProt-enrichment path (the behavior these inject tests exercise)."""

    async def exec(self, _stmt):
        return _ExecResult(None)

    def add(self, _obj):
        pass

    async def commit(self):
        pass


@pytest.mark.asyncio
async def test_persist_validated_targets_persists_validated():
    """Targets with a UniProt accession are inserted into the targets table."""
    from app.models.target import Target
    from app.services.target_persist import persist_validated_targets

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None  # not yet in DB
    mock_session.exec.return_value = mock_result

    count = await persist_validated_targets(VALIDATED_TARGETS, mock_session)

    assert count == 2
    assert mock_session.add.call_count == 2
    for added_call in mock_session.add.call_args_list:
        obj = added_call.args[0]
        assert isinstance(obj, Target), f"Expected Target, got {type(obj)}"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_persist_validated_targets_skips_unvalidated():
    """Targets without a UniProt accession (skip_validation) are not persisted."""
    from app.services.target_persist import persist_validated_targets

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None
    mock_session.exec.return_value = mock_result

    count = await persist_validated_targets(UNVALIDATED_TARGETS, mock_session)

    assert count == 0
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_persist_validated_targets_skips_existing():
    """If a target_id already exists in DB, it is not inserted again."""
    from app.models.target import Target
    from app.services.target_persist import persist_validated_targets

    mock_session = AsyncMock()
    existing = MagicMock(spec=Target)
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = existing
    mock_session.exec.return_value = mock_result

    count = await persist_validated_targets(VALIDATED_TARGETS, mock_session)

    assert count == 0
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_persist_validated_targets_no_link_rows():
    """Caching must never create CompoundTarget or DiseaseTarget association rows."""
    from app.models.target import CompoundTarget, DiseaseTarget
    from app.services.target_persist import persist_validated_targets

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None
    mock_session.exec.return_value = mock_result

    await persist_validated_targets(VALIDATED_TARGETS, mock_session)

    for added_call in mock_session.add.call_args_list:
        obj = added_call.args[0]
        assert not isinstance(obj, (CompoundTarget, DiseaseTarget)), \
            "Must NOT add link rows during caching"


@pytest.mark.asyncio
async def test_persist_canonical_target_inserts_absent_skips_present_no_commit():
    """Primitive inserts an absent target, skips a present one, creates no link
    rows, and never commits (the caller owns commit granularity)."""
    from app.models.target import CompoundTarget, DiseaseTarget, Target
    from app.services.target_persist import persist_canonical_target

    absent = Target(
        target_id="uniprot:P04637",
        canonical_key="uniprot:P04637",
        gene_symbol="TP53",
        uniprot_accession="P04637",
    )
    present = Target(
        target_id="uniprot:P00533",
        canonical_key="uniprot:P00533",
        gene_symbol="EGFR",
        uniprot_accession="P00533",
    )

    # First SELECT (absent) -> None; second SELECT (present) -> an existing row.
    miss = MagicMock()
    miss.one_or_none.return_value = None
    hit = MagicMock()
    hit.one_or_none.return_value = MagicMock(spec=Target)

    mock_session = AsyncMock()
    mock_session.exec.side_effect = [miss, hit]

    count = await persist_canonical_target([absent, present], mock_session)

    assert count == 1
    mock_session.add.assert_called_once()
    added = mock_session.add.call_args.args[0]
    assert added is absent
    assert not isinstance(added, (CompoundTarget, DiseaseTarget))
    # Primitive must NOT commit — commit granularity is the caller's.
    mock_session.commit.assert_not_called()


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
async def test_persist_validated_targets_db_error_returns_zero():
    """If the DB raises during caching, the function returns 0 (does not re-raise)."""
    from app.services.target_persist import persist_validated_targets

    mock_session = AsyncMock()
    mock_session.exec.side_effect = Exception("DB connection lost")

    count = await persist_validated_targets(VALIDATED_TARGETS, mock_session)
    assert count == 0


@pytest.mark.asyncio
async def test_inject_targets_validated_path_reports_cached():
    """inject_targets_service validated path calls the cache and surfaces its count."""
    from app.schemas.analysis import InjectTargetsRequest
    from app.services.manual_inputs import inject_targets_service

    run = MagicMock()
    run.analysis_id = UUID("00000000-0000-0000-0000-000000000044")
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    tp53 = MagicMock()
    tp53.gene_symbol = "TP53"
    tp53.uniprot_accession = "P04637"
    tp53.protein_name = "Cellular tumor antigen p53"

    # inject_targets_service now routes through resolve_targets, which owns the UniProt
    # call, the DB-first lookup, and persistence. The response `cached` count is
    # reused+enriched; a single novel enriched target → cached=1. We mock UniProt and
    # persistence inside input_validation and feed a DB-miss session.
    import app.services.gene_symbols as gs
    gs._MAP = {"TP53": {"symbol": "TP53", "kind": "approved"}}
    try:
        with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
             patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()), \
             patch("app.services.input_validation.validate_human_target", new=AsyncMock(return_value=tp53)), \
             patch("app.services.input_validation.persist_validated_targets", new=AsyncMock(return_value=1)) as mock_cache:

            request = InjectTargetsRequest(targets=["TP53"])
            result = await inject_targets_service(request.targets, request.skip_validation, run, _FakeSession())
    finally:
        gs._MAP = None

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
    import app.services.gene_symbols as gs
    from app.schemas.analysis import InjectTargetsRequest
    from app.services.manual_inputs import inject_targets_service

    gs._MAP = {
        "TNFA": {"symbol": "TNF", "kind": "alias"},
        "TP53": {"symbol": "TP53", "kind": "approved"},
    }
    run = MagicMock()
    run.analysis_id = UUID("00000000-0000-0000-0000-000000000055")
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    captured = {}

    async def _capture_status(session, aid, status=None, stage_results=None):
        captured["stage3"] = stage_results["stage_3"]
        return run

    # Lenient symbols are offline-normalized (TNFA→TNF, recorded in normalized) then
    # enriched via UniProt on a DB miss. Mock UniProt to resolve both canonical symbols.
    async def fake_validate(gene_symbol=None, uniprot_id=None):
        info = MagicMock()
        info.gene_symbol = gene_symbol
        info.uniprot_accession = "P01375" if gene_symbol == "TNF" else "P04637"
        info.protein_name = None
        return info

    with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(side_effect=_capture_status)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.input_validation.validate_human_target", new=AsyncMock(side_effect=fake_validate)), \
         patch("app.services.input_validation.persist_validated_targets", new=AsyncMock(return_value=0)):
        request = InjectTargetsRequest(targets=["TNFA", "TP53"], skip_validation=True)
        result = await inject_targets_service(request.targets, request.skip_validation, run, _FakeSession())

    assert result.injected == 2
    assert {"from": "TNFA", "to": "TNF"} in result.normalized
    symbols = captured["stage3"]["target_gene_symbols"]
    assert "TNF" in symbols and "TP53" in symbols
    assert "TNFA" not in symbols  # alias was canonicalized
    gs._MAP = None


@pytest.mark.asyncio
async def test_inject_targets_lenient_dedups_alias_and_canonical():
    """Submitting an alias and its canonical collapses to one target after normalization."""
    import app.services.gene_symbols as gs
    from app.schemas.analysis import InjectTargetsRequest
    from app.services.manual_inputs import inject_targets_service

    gs._MAP = {"TNFA": {"symbol": "TNF", "kind": "alias"}, "TNF": {"symbol": "TNF", "kind": "approved"}}
    run = MagicMock()
    run.analysis_id = UUID("00000000-0000-0000-0000-000000000056")
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    # Both inputs normalize to canonical TNF → same dedup key → second collapses.
    # The first (TNF) enriches via UniProt on a DB miss.
    async def fake_validate(gene_symbol=None, uniprot_id=None):
        info = MagicMock()
        info.gene_symbol = "TNF"
        info.uniprot_accession = "P01375"
        info.protein_name = None
        return info

    with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.input_validation.validate_human_target", new=AsyncMock(side_effect=fake_validate)), \
         patch("app.services.input_validation.persist_validated_targets", new=AsyncMock(return_value=0)):
        request = InjectTargetsRequest(targets=["TNF", "TNFA"], skip_validation=True)
        result = await inject_targets_service(request.targets, request.skip_validation, run, _FakeSession())

    assert result.injected == 1
    assert result.duplicates_removed == 1
    gs._MAP = None


@pytest.mark.asyncio
async def test_inject_targets_lenient_unknown_kept_and_flagged():
    """An unknown symbol is kept (injected) but reported in unrecognized[]."""
    import app.services.gene_symbols as gs
    from app.schemas.analysis import InjectTargetsRequest
    from app.services.manual_inputs import inject_targets_service

    gs._MAP = {"TP53": {"symbol": "TP53", "kind": "approved"}}
    run = MagicMock()
    run.analysis_id = UUID("00000000-0000-0000-0000-000000000057")
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    # ZZZ9 is an unknown symbol: offline-normalize leaves it as-is, the DB lookup
    # misses, and UniProt can't resolve it (ValueError). Lenient mode keeps it and
    # flags it manual_unrecognized rather than failing it.
    async def fake_validate(gene_symbol=None, uniprot_id=None):
        raise ValueError(f"Gene symbol {gene_symbol!r} not found as human protein")

    with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.input_validation.validate_human_target", new=AsyncMock(side_effect=fake_validate)), \
         patch("app.services.input_validation.persist_validated_targets", new=AsyncMock(return_value=0)):
        request = InjectTargetsRequest(targets=["ZZZ9"], skip_validation=True)
        result = await inject_targets_service(request.targets, request.skip_validation, run, _FakeSession())

    assert result.injected == 1
    assert result.unrecognized == ["ZZZ9"]
    gs._MAP = None


@pytest.mark.asyncio
async def test_inject_targets_lenient_accession_routes_to_uniprot():
    """A UniProt accession in lenient mode is resolved via UniProt, not the offline map."""
    import app.services.gene_symbols as gs
    from app.schemas.analysis import InjectTargetsRequest
    from app.services.manual_inputs import inject_targets_service

    gs._MAP = {}
    info = MagicMock()
    info.gene_symbol = "TP53"
    info.uniprot_accession = "P04637"
    info.protein_name = "Cellular tumor antigen p53"

    run = MagicMock()
    run.analysis_id = UUID("00000000-0000-0000-0000-000000000058")
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()), \
         patch("app.services.input_validation.validate_human_target", new=AsyncMock(return_value=info)) as mock_val, \
         patch("app.services.input_validation.persist_validated_targets", new=AsyncMock(return_value=1)):
        request = InjectTargetsRequest(targets=["P04637"], skip_validation=True)
        result = await inject_targets_service(request.targets, request.skip_validation, run, _FakeSession())

    mock_val.assert_awaited_once()
    assert result.injected == 1
    gs._MAP = None


@pytest.mark.asyncio
async def test_inject_targets_lenient_accession_uniprot_down_maps_503():
    """A UniProt outage while resolving an accession (even in lenient mode) maps to 503.

    BEHAVIOR CHANGE: the old hand-rolled lenient path silently kept+flagged an
    accession when UniProt was down (no 503). The unified resolve_targets instead
    treats a provider outage as a transient, retriable condition — it re-raises
    ServiceUnavailableError, which inject_targets_service maps to HTTP 503. An outage
    must not masquerade as a permanently-unrecognized target. (Offline symbol
    normalization is unaffected; only accession/symbol *enrichment* needs UniProt.)"""
    import app.services.gene_symbols as gs
    from app.schemas.analysis import InjectTargetsRequest
    from app.services.manual_inputs import inject_targets_service
    from fastapi import HTTPException
    from integrations._retry import ServiceUnavailableError

    gs._MAP = {}
    run = MagicMock()
    run.analysis_id = UUID("00000000-0000-0000-0000-000000000059")
    run.status = "pending"
    run.parameters = {}
    run.stage_results = {}

    try:
        with patch("app.services.manual_inputs.analysis_repo.update_run_status", new=AsyncMock(return_value=run)), \
             patch("app.services.manual_inputs.analysis_repo.merge_run_parameters", new=AsyncMock()), \
             patch("app.services.input_validation.validate_human_target", new=AsyncMock(side_effect=ServiceUnavailableError("down"))), \
             patch("app.services.input_validation.persist_validated_targets", new=AsyncMock(return_value=0)):
            request = InjectTargetsRequest(targets=["P04637"], skip_validation=True)
            with pytest.raises(HTTPException) as ei:
                await inject_targets_service(request.targets, request.skip_validation, run, _FakeSession())
        assert ei.value.status_code == 503
    finally:
        gs._MAP = None
