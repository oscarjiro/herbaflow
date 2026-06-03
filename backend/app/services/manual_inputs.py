"""Service layer for manual compound injection (inject-compounds endpoint)."""
from __future__ import annotations

import logging

import httpx
from integrations._retry import ServiceUnavailableError
from integrations.pubchem_compound import validate_compounds_batch
from app.errors import PUBCHEM_UNAVAILABLE
from app.repositories import analysis_repo
from app.schemas.analysis import InjectCompoundsResponse
from app.services.compound_dedup import deduplicate_compounds

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
    from app.services.compound_persist import persist_validated_compounds

    analysis_id = run.analysis_id

    # Collect compound IDs already present in this analysis (stage_1 results)
    existing_stage1 = (run.stage_results or {}).get("stage_1") or {}
    existing_ids: set[str] = set(existing_stage1.get("compound_ids", []))

    # Single shared client for both dedup PubChem lookups and batch validation.
    async with httpx.AsyncClient(timeout=20.0) as client:
        # Deduplicate submitted inputs against each other and existing stage_1 compounds
        try:
            deduped_inputs, dedup_removed = await deduplicate_compounds(
                submitted=compounds,
                existing_ids=existing_ids,
                client=client,
            )
        except Exception as e:
            logger.warning("Deduplication failed, proceeding with raw inputs: %s", e, exc_info=True)
            deduped_inputs = compounds
            dedup_removed = []

        if not deduped_inputs:
            return InjectCompoundsResponse(
                injected=0,
                failed=[],
                duplicates_removed=len(dedup_removed),
                duplicate_names=dedup_removed,
                cached=0,
            )

        try:
            validated, failed = await validate_compounds_batch(deduped_inputs, client)
        except ServiceUnavailableError as e:
            logger.error("PubChem batch validation error: %s", e, exc_info=True)
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail=PUBCHEM_UNAVAILABLE)
        except Exception as e:
            logger.error("PubChem batch validation error: %s", e, exc_info=True)
            from fastapi import HTTPException
            raise HTTPException(status_code=502, detail=PUBCHEM_UNAVAILABLE)

    if not validated:
        return InjectCompoundsResponse(
            injected=0,
            failed=failed,
            duplicates_removed=len(dedup_removed),
            duplicate_names=dedup_removed,
            cached=0,
        )

    # Persist canonicalized compounds to DB for future pipeline reuse.
    # Non-fatal: if persistence fails, log a warning and continue.
    cached_count = await persist_validated_compounds(validated, session)

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
    }

    # Build stage_2 synthetic result — mimics stage2_adme.run() output.
    pass_count = sum(1 for c in validated if c.get("adme_pass"))
    stage2_compounds = [
        {
            "compound_id": c["compound_id"],
            "canonical_name": c["canonical_name"],
            "plant_ids": [],
            "adme_pass": c["adme_pass"],
            "is_np_exception": c["is_np_exception"],
            "is_pains_positive": c["is_pains_positive"],
            "molecular_weight": c["molecular_weight"],
            "logp": c["logp"],
            "tpsa": c["tpsa"],
            "hbond_donors": c["hbond_donors"],
            "hbond_acceptors": c["hbond_acceptors"],
            "np_likeness_score": c["np_likeness_score"],
            "rotatable_bonds": c["rotatable_bonds"],
        }
        for c in validated
    ]
    # Stage 3 reads all_active_compound_ids from stage_2 to get its work list.
    # For manual input all validated compounds are "active" (ADME filter already applied).
    stage2_result = {
        "passed": pass_count,
        "failed": len(validated) - pass_count,
        "np_exceptions": 0,
        "passed_compound_ids": [c["compound_id"] for c in validated if c.get("adme_pass")],
        "np_exception_compound_ids": [],
        "all_active_compound_ids": compound_ids,  # stage 3 reads this
        "compounds": stage2_compounds,
    }

    await analysis_repo.update_run_status(
        session,
        analysis_id,
        status=run.status,  # leave status unchanged — pipeline not started yet
        stage_results={"stage_1": stage1_result, "stage_2": stage2_result},
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
        duplicates_removed=len(dedup_removed),
        duplicate_names=dedup_removed,
        cached=cached_count,
    )
