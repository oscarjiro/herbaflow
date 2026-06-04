"""Canonicalization invariant for the STP import-targets handler.

The import-targets handler must build the persisted Target's id AND canonical_key
through the canonicalization core, so the two can never disagree for the same row.
An imported accession that is lowercase and/or carries an isoform suffix
(e.g. 'p04637-2') must persist as the canonical parent:

    target_id     == make_target_id("P04637")
    canonical_key == target_canonical_key("p04637-2") == "uniprot:P04637"

Pre-fix, the handler set canonical_key from the raw field (f"uniprot:{uniprot_id}"),
so the id (folded by the core) and key (raw) drifted apart.
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from app.schemas.import_targets import ImportTargetsRequest, STPTarget
from app.services.canonicalize import make_target_id, target_canonical_key


def _run_with_compound(compound_id: str):
    """Minimal analysis run whose stage results let import_targets reach its loop."""
    run = MagicMock()
    run.status = "running"
    run.stage_results = {
        "stage_2": {"all_active_compound_ids": [compound_id]},
        "stage_3": {
            "covered": 0,
            "no_data": 1,
            "target_count": 0,
            "target_gene_symbols": [],
            "target_compound_map": {},
            "coverage_pct": 0.0,
            "targets": [],
            "compound_sources": {},
            "uncovered_compounds": [
                {"compound_id": compound_id, "canonical_name": "C", "smiles": "CC"}
            ],
        },
    }
    return run


@pytest.mark.asyncio
async def test_import_targets_canonicalizes_isoform_and_case():
    """A lowercase + isoform STP accession persists as the canonical parent target."""
    from app.routers.analyses import import_targets

    compound_id = "cid-B"
    run = _run_with_compound(compound_id)

    # exec().one_or_none() -> None so both upserts (Target, CompoundTarget) insert.
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None
    mock_session.exec.return_value = mock_result

    # Raw, non-canonical accession: lowercase + isoform suffix. Bypass the schema
    # validator (which would reject/normalize it) to assert the HANDLER canonicalizes.
    stp = STPTarget.model_construct(uniprot_id="p04637-2", gene_symbol="tp53", probability=0.5)
    request = ImportTargetsRequest.model_construct(compound_id=compound_id, targets=[stp])

    with patch("app.routers.analyses.analysis_repo.get_run", new=AsyncMock(return_value=run)), \
         patch("app.routers.analyses.analysis_repo.update_run_status", new=AsyncMock(return_value=run)):
        result = await import_targets(UUID("00000000-0000-0000-0000-0000000000aa"), request, mock_session)

    assert result.imported == 1

    # Capture the persisted Target row from session.add(...).
    from app.models.target import Target
    added_targets = [
        c.args[0] for c in mock_session.add.call_args_list if isinstance(c.args[0], Target)
    ]
    assert len(added_targets) == 1, "exactly one Target row should be persisted"
    target = added_targets[0]

    # Invariant: id and key are both canonical and mutually consistent.
    assert target.target_id == make_target_id("P04637")
    assert target.canonical_key == target_canonical_key("p04637-2")
    assert target.canonical_key == "uniprot:P04637"
