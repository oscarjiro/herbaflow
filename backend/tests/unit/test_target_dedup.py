"""Tests for target deduplication — service layer and inject_targets endpoint wiring.

Covers:
1. Gene symbol + UniProt accession for same protein → only one added (canonical dedup)
2. Same gene symbol submitted twice → only one added (within-batch dedup)
3. Target already in existing stage_3 results → not added again (cross-analysis dedup)
4. Response includes added/duplicates_removed/duplicate_names
5. UniProt unavailable → graceful string-based fallback (no crash)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

ANALYSIS_ID = "00000000-0000-0000-0000-000000000099"


def _make_uniprot_target(gene: str, accession: str, protein_name: str | None = None):
    t = MagicMock()
    t.gene_symbol = gene
    t.uniprot_accession = accession
    t.protein_name = protein_name
    return t


def _make_run(status: str = "pending") -> MagicMock:
    from uuid import UUID
    run = MagicMock()
    run.analysis_id = UUID(ANALYSIS_ID)
    run.status = status
    run.parameters = {}
    run.stage_results = {}
    return run


# ---------------------------------------------------------------------------
# Service-layer unit tests (no HTTP / no DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_gene_symbol_and_accession_same_protein():
    """Gene symbol + UniProt accession for same protein → only one entry kept.

    Submitting ["TP53", "P04637"] where both resolve to the same canonical
    accession P04637 must produce unique_new=1, duplicates=1.
    """
    from app.services.target_dedup import deduplicate_targets

    tp53_target = _make_uniprot_target("TP53", "P04637")

    async def fake_validate(gene_symbol=None, uniprot_id=None):
        return tp53_target

    submitted = [
        {"gene_symbol": "TP53"},
        {"uniprot_id": "P04637"},
    ]

    with patch("app.services.target_dedup.validate_human_target",
               new=AsyncMock(side_effect=fake_validate)):
        unique_new, duplicates = await deduplicate_targets(
            submitted=submitted,
            existing_ids=set(),
        )

    assert len(unique_new) == 1
    assert len(duplicates) == 1
    # The duplicate label should identify the removed entry
    assert duplicates[0] in ("P04637", "TP53")


@pytest.mark.asyncio
async def test_dedup_same_gene_symbol_twice():
    """Same gene symbol submitted twice → only one added."""
    from app.services.target_dedup import deduplicate_targets

    tp53_target = _make_uniprot_target("TP53", "P04637")

    submitted = [
        {"gene_symbol": "TP53"},
        {"gene_symbol": "TP53"},
    ]

    with patch("app.services.target_dedup.validate_human_target",
               new=AsyncMock(return_value=tp53_target)):
        unique_new, duplicates = await deduplicate_targets(
            submitted=submitted,
            existing_ids=set(),
        )

    assert len(unique_new) == 1
    assert len(duplicates) == 1


@pytest.mark.asyncio
async def test_dedup_against_existing_ids():
    """Target already in existing analysis results → not added again."""
    from app.services.target_dedup import deduplicate_targets

    tp53_target = _make_uniprot_target("TP53", "P04637")
    # P04637 is already in the pipeline results
    existing_ids = {"P04637"}

    submitted = [{"gene_symbol": "TP53"}]

    with patch("app.services.target_dedup.validate_human_target",
               new=AsyncMock(return_value=tp53_target)):
        unique_new, duplicates = await deduplicate_targets(
            submitted=submitted,
            existing_ids=existing_ids,
        )

    assert len(unique_new) == 0
    assert len(duplicates) == 1
    assert duplicates[0] == "TP53"


@pytest.mark.asyncio
async def test_dedup_response_summary_fields():
    """inject_targets_service must return duplicates_removed and duplicate_names."""
    from app.schemas.analysis import InjectTargetsRequest
    from app.services.manual_inputs import inject_targets_service

    run = _make_run(status="pending")
    captured_stage_results: dict = {}

    async def fake_update(session, analysis_id, status, **kwargs):
        if "stage_results" in kwargs:
            captured_stage_results.update(kwargs["stage_results"])
        return run

    tp53_target = _make_uniprot_target("TP53", "P04637")
    egfr_target = _make_uniprot_target("EGFR", "P00533")

    async def fake_validate(gene_symbol=None, uniprot_id=None):
        if gene_symbol == "TP53" or uniprot_id == "P04637":
            return tp53_target
        return egfr_target

    # Submit TP53 and its accession P04637 — should deduplicate to 1
    with patch("app.services.manual_inputs.analysis_repo.update_run_status",
               new=AsyncMock(side_effect=fake_update)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters",
               new=AsyncMock()), \
         patch("app.services.target_dedup.validate_human_target",
               new=AsyncMock(side_effect=fake_validate)), \
         patch("app.services.manual_inputs.validate_human_target",
               new=AsyncMock(side_effect=fake_validate)), \
         patch("app.services.target_persist.persist_validated_targets",
               new=AsyncMock(return_value=0)):

        mock_session = AsyncMock()
        request = InjectTargetsRequest(targets=["TP53", "P04637"])
        result = await inject_targets_service(request.targets, request.skip_validation, run, mock_session)

    # Response must have dedup summary fields
    assert hasattr(result, "duplicates_removed"), "Response missing duplicates_removed"
    assert hasattr(result, "duplicate_names"), "Response missing duplicate_names"
    assert result.duplicates_removed == 1
    assert len(result.duplicate_names) == 1


@pytest.mark.asyncio
async def test_dedup_uniprot_unavailable_fallback():
    """When UniProt is unavailable during dedup, fall back to lowercased string comparison."""
    from app.services.target_dedup import deduplicate_targets
    from integrations._retry import ServiceUnavailableError

    async def raise_unavailable(gene_symbol=None, uniprot_id=None):
        raise ServiceUnavailableError("UniProt is down")

    # Two entries that look like the same gene (lowercased match)
    submitted = [
        {"gene_symbol": "TP53"},
        {"gene_symbol": "tp53"},  # same protein, different case
    ]

    with patch("app.services.target_dedup.validate_human_target",
               new=AsyncMock(side_effect=raise_unavailable)):
        # Should NOT raise — must gracefully fall back
        unique_new, duplicates = await deduplicate_targets(
            submitted=submitted,
            existing_ids=set(),
        )

    # Fallback: lowercased gene_symbol used — "tp53" == "tp53" → duplicate
    assert len(unique_new) == 1
    assert len(duplicates) == 1


@pytest.mark.asyncio
async def test_dedup_no_canonicalization_possible_include_as_is():
    """Entry with no gene_symbol or uniprot_id → included as-is (graceful)."""
    from app.services.target_dedup import deduplicate_targets

    submitted = [
        {},  # no fields — no canonicalization possible
        {"gene_symbol": "TP53"},
    ]

    tp53_target = _make_uniprot_target("TP53", "P04637")

    with patch("app.services.target_dedup.validate_human_target",
               new=AsyncMock(return_value=tp53_target)):
        unique_new, duplicates = await deduplicate_targets(
            submitted=submitted,
            existing_ids=set(),
        )

    # Both should pass through — the empty dict has no canonical key to deduplicate against
    assert len(unique_new) == 2
    assert len(duplicates) == 0
