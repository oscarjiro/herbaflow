"""Service layer for manual compound/target injection endpoints.

Both injection paths route through the unified DB-first resolution service
(``app.services.input_validation``): ``resolve_compounds`` for compounds and
``resolve_targets`` for targets. The unified service owns classification, DB-first
reuse, provider enrichment, dedup, and persistence; this module is a thin adapter
that maps a ``ResolveResult`` onto the synthetic stage_1 / stage_3 results and the
inject-response schemas. Result SHAPES are unchanged from the previous
hand-rolled implementation.
"""
from __future__ import annotations

import logging

import httpx
from integrations._retry import ServiceUnavailableError

from app.errors import UNIPROT_UNAVAILABLE
from app.repositories import analysis_repo
from app.schemas.analysis import InjectCompoundsResponse, InjectTargetsResponse
from app.services.input_validation import resolve_compounds, resolve_targets

logger = logging.getLogger(__name__)


async def inject_compounds_service(
    compounds: list[str],
    run,          # AnalysisRun, already fetched + guarded by the caller
    session,
) -> InjectCompoundsResponse:
    """Core logic for manual-compound injection.

    Receives a pre-fetched, pre-guarded run and session.  The HTTP endpoint
    (analyses router) is responsible for the 404/409 guards and for passing
    ``body.compounds`` as ``compounds``.
    """
    analysis_id = run.analysis_id

    # Collect compound IDs already present in this analysis (stage_1 results) —
    # these seed the unified service's dedup seen-set (keys are canonical compound_ids).
    existing_stage1 = (run.stage_results or {}).get("stage_1") or {}
    existing_keys: set[str] = set(existing_stage1.get("compound_ids", []))

    # Single shared client for the unified service's PubChem round-trips.
    # resolve_compounds owns classification, DB-first reuse, dedup, and persistence.
    async with httpx.AsyncClient(timeout=20.0) as client:
        result = await resolve_compounds(
            compounds,
            existing_keys=existing_keys,
            session=session,
            client=client,
        )

    validated = result.valid
    failed = [f.input for f in result.failed]

    if not validated:
        return InjectCompoundsResponse(
            injected=0,
            failed=failed,
            duplicates_removed=len(result.duplicates),
            duplicate_names=result.duplicates,
            cached=0,
        )

    # Build stage_1 synthetic result — mimics stage1_selection.run() output.
    # Stage 2 reads compound_ids from stage_1; stage 3 reads all_active_compound_ids
    # from stage_2. We populate both so the chain works unchanged.
    compound_ids = [c["compound_id"] for c in validated]

    stage1_compounds = [
        {
            "compound_id": c["compound_id"],
            "canonical_name": c["canonical_name"],
            "plant_ids": [],  # no plant source for manual input
        }
        for c in validated
    ]
    stage1_result = {
        "compound_ids": compound_ids,
        "compound_count": len(validated),
        "plant_ids": [],
        "total_compounds": len(validated),
        "plants_covered": 0,
        "compounds": stage1_compounds,
        # Store full property data for downstream use (inchikey, mw, etc.)
        "_manual_compounds": validated,
        "state": "user_provided",
        "inputs": {"rejected": failed, "normalized": [], "unrecognized": []},
    }

    await analysis_repo.update_run_status(
        session,
        analysis_id,
        status=run.status,  # leave status unchanged — pipeline not started yet
        stage_results={"stage_1": stage1_result},
    )
    # Persist manual_compound_ids so stage2_adme.run() can identify them and
    # apply the ADME bypass when apply_adme_to_manual=False.  Merge with any
    # IDs already present (idempotent — repeated inject calls accumulate IDs).
    existing_manual_ids: list[str] = (run.parameters or {}).get("manual_compound_ids", [])
    merged_manual_ids = list(dict.fromkeys(existing_manual_ids + compound_ids))
    await analysis_repo.merge_run_parameters(
        session,
        analysis_id,
        {"_input_mode": "manual_compounds", "manual_compound_ids": merged_manual_ids},
    )

    return InjectCompoundsResponse(
        injected=len(validated),
        failed=failed,
        duplicates_removed=len(result.duplicates),
        duplicate_names=result.duplicates,
        # `cached` = compounds backed by the canonical DB cache. resolve_compounds
        # persists internally, so every valid compound is now cache-backed;
        # reused (DB hit) + enriched (newly persisted) == len(validated).
        cached=result.reused + result.enriched,
    )


async def inject_targets_service(
    targets: list[str],
    skip_validation: bool,
    run,          # AnalysisRun, already fetched + guarded by the caller
    session,
) -> "InjectTargetsResponse":
    """Core logic for manual-target injection.

    Receives a pre-fetched, pre-guarded run and session.  The HTTP endpoint
    (analyses router) is responsible for the 404/409 guards and for passing
    ``body.targets`` as ``targets`` and ``body.skip_validation`` as
    ``skip_validation``.

    Routes through the unified ``resolve_targets`` service: a single call handles
    both the strict (UniProt round-trip per novel input) and lenient
    (``skip_validation`` — offline HGNC normalize, keep+flag unknowns) paths.
    """
    analysis_id = run.analysis_id

    # Existing stage_3 targets are preserved and accumulated across repeated calls.
    existing_stage3 = (run.stage_results or {}).get("stage_3") or {}
    existing_targets_full: list[dict] = list(existing_stage3.get("targets", []))

    # Seed the unified service's dedup seen-set with keys already present:
    # uppercased UniProt accessions AND canonical gene symbols.
    existing_keys: set[str] = set()
    for t in existing_targets_full:
        acc = t.get("uniprot_id")
        if acc:
            existing_keys.add(acc.upper())
        sym = t.get("gene_symbol")
        if sym:
            existing_keys.add(sym.upper())

    # resolve_targets owns classification, DB-first reuse, UniProt enrichment, dedup,
    # and persistence. A provider outage raises ServiceUnavailableError → HTTP 503.
    try:
        result = await resolve_targets(
            targets,
            lenient=skip_validation,
            existing_keys=existing_keys,
            session=session,
        )
    except ServiceUnavailableError as exc:
        logger.error("UniProt unavailable during inject-targets: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=UNIPROT_UNAVAILABLE)

    new_targets = result.valid  # already excludes existing/dup keys
    failed = [f.input for f in result.failed]
    unrecognized = [
        t["gene_symbol"] for t in new_targets if "manual_unrecognized" in t["sources"]
    ]

    if not new_targets:
        return InjectTargetsResponse(
            injected=0,
            failed=failed,
            duplicates_removed=len(result.duplicates),
            duplicate_names=result.duplicates,
            cached=0,
            normalized=result.normalized,
            unrecognized=unrecognized,
        )

    # Merge with existing stage_3 targets so repeated batch calls accumulate.
    all_targets = existing_targets_full + new_targets

    # Build synthetic stage_3 result — stage 5 reads target_gene_symbols.
    stage3_result = {
        "target_count": len(all_targets),
        "target_ids": [t["target_id"] for t in all_targets],
        "target_gene_symbols": [t["gene_symbol"] for t in all_targets],
        # Manual targets have no associated compounds — empty list is correct
        "target_compound_map": {t["gene_symbol"]: [] for t in all_targets},
        "targets": all_targets,
        # Coverage fields (not meaningful for manual input)
        "covered": len(all_targets),
        "no_data": 0,
        "coverage_pct": 100.0,
        "compound_sources": {},
        "uncovered_compounds": [],
        "state": "user_provided",
        "inputs": {
            "rejected": failed,
            "normalized": result.normalized,
            "unrecognized": unrecognized,
        },
    }

    await analysis_repo.update_run_status(
        session,
        analysis_id,
        status=run.status,  # leave status unchanged — pipeline not started yet
        stage_results={"stage_3": stage3_result},
    )
    await analysis_repo.merge_run_parameters(
        session,
        analysis_id,
        {"_input_mode": "manual_targets"},
    )

    # resolve_targets already persisted newly enriched targets that carry a UniProt
    # accession — no explicit persist call here (avoids a double-persist).
    return InjectTargetsResponse(
        injected=len(new_targets),
        failed=failed,
        duplicates_removed=len(result.duplicates),
        duplicate_names=result.duplicates,
        # `cached` = targets backed by the canonical DB cache (DB hits + newly
        # persisted enrichments). symbol-only unrecognized targets are not persisted.
        cached=result.reused + result.enriched,
        normalized=result.normalized,
        unrecognized=unrecognized,
    )
