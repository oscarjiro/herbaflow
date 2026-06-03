"""Service layer for manual compound/target injection endpoints."""
from __future__ import annotations

import logging
import re
import asyncio

import httpx
from integrations._retry import ServiceUnavailableError
from integrations.pubchem_compound import validate_compounds_batch
from integrations.uniprot import validate_human_target
from app.errors import PUBCHEM_UNAVAILABLE, UNIPROT_UNAVAILABLE
from app.repositories import analysis_repo
from app.schemas.analysis import InjectCompoundsResponse, InjectTargetsResponse
from app.services.compound_dedup import deduplicate_compounds
from analysis.stages.stage3_targets import _make_target_id

logger = logging.getLogger(__name__)

_UNIPROT_ACCESSION_RE = re.compile(
    r"^[OPQ][0-9][A-Z0-9]{3}[0-9](?:[A-Z][A-Z0-9]{2}[0-9])?$"
    r"|^[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}$",
    re.IGNORECASE,
)

_INJECT_TARGETS_ALLOWED = re.compile(r"^(pending|failed|stage_[1-4]_awaiting_approval)$")


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
    """
    from app.services.target_dedup import deduplicate_targets

    analysis_id = run.analysis_id

    # Collect UniProt accessions already in stage_3 results for cross-analysis dedup
    existing_stage3 = (run.stage_results or {}).get("stage_3") or {}
    existing_targets_full: list[dict] = list(existing_stage3.get("targets", []))
    existing_ids: set[str] = {
        t.get("uniprot_id", "").upper()
        for t in existing_targets_full
        if t.get("uniprot_id")
    }
    # Ensure existing_ids is normalized to uppercase for consistent dedup
    existing_ids = {key.upper() for key in existing_ids if key}

    # Convert flat string inputs to dicts for the dedup service.
    # Each input is either a UniProt accession or a gene symbol.
    submitted_dicts: list[dict] = []
    for raw in targets:
        raw_stripped = raw.strip()
        if not raw_stripped:
            submitted_dicts.append({"_raw": raw})
            continue
        is_accession = bool(_UNIPROT_ACCESSION_RE.match(raw_stripped))
        if is_accession:
            submitted_dicts.append({"uniprot_id": raw_stripped, "_raw": raw})
        else:
            submitted_dicts.append({"gene_symbol": raw_stripped, "_raw": raw})

    # skip_validation bypasses UniProt entirely — no dedup needed either
    if skip_validation:
        deduped_dicts = submitted_dicts
        dedup_removed_labels = []
    else:
        # Deduplicate before validation — removes within-batch and cross-analysis dups
        try:
            deduped_dicts, dedup_removed_labels = await deduplicate_targets(
                submitted=submitted_dicts,
                existing_ids=existing_ids,
            )
        except Exception as exc:
            logger.warning("Target deduplication failed, proceeding without dedup: %s", exc, exc_info=True)
            deduped_dicts = submitted_dicts
            dedup_removed_labels = []

    if not deduped_dicts:
        return InjectTargetsResponse(
            injected=0,
            failed=[],
            duplicates_removed=len(dedup_removed_labels),
            duplicate_names=dedup_removed_labels,
        )

    # Lenient path: normalize gene symbols offline (HGNC), resolve accessions via UniProt,
    # never drop inputs (unknowns kept + flagged), normalize-then-dedup by canonical symbol.
    if skip_validation:
        from app.services import gene_symbols
        from app.services.target_persist import persist_validated_targets

        normalized_changes: list[dict] = []
        unrecognized: list[str] = []
        lenient_targets: list[dict] = []

        for entry in deduped_dicts:
            raw = entry.get("_raw", entry.get("gene_symbol") or entry.get("uniprot_id") or "")
            raw_stripped = raw.strip() if isinstance(raw, str) else ""
            if not raw_stripped:
                continue

            if entry.get("uniprot_id"):
                # Accession -> UniProt (only authority for secondary/obsolete accessions).
                try:
                    info = await validate_human_target(gene_symbol=None, uniprot_id=raw_stripped)
                    lenient_targets.append({
                        "target_id": _make_target_id(info.uniprot_accession, info.gene_symbol),
                        "gene_symbol": info.gene_symbol,
                        "uniprot_id": info.uniprot_accession,
                        "protein_name": info.protein_name,
                        "compound_ids": [],
                        "sources": ["manual"],
                    })
                except (ValueError, ServiceUnavailableError):
                    # Lenient: never block the run on accession resolution — keep + flag.
                    acc = raw_stripped.upper()
                    unrecognized.append(raw_stripped)
                    lenient_targets.append({
                        "target_id": f"manual:{acc}",
                        "gene_symbol": acc,
                        "uniprot_id": None,
                        "protein_name": None,
                        "compound_ids": [],
                        "sources": ["manual_unrecognized"],
                    })
            else:
                res = gene_symbols.normalize(raw_stripped)
                if res.status == "unrecognized":
                    unrecognized.append(raw_stripped)
                    source = "manual_unrecognized"
                else:
                    if res.canonical != raw_stripped.upper():
                        normalized_changes.append({"from": raw_stripped, "to": res.canonical})
                    source = "manual_normalized"
                lenient_targets.append({
                    "target_id": f"manual:{res.canonical}",
                    "gene_symbol": res.canonical,
                    "uniprot_id": None,
                    "protein_name": None,
                    "compound_ids": [],
                    "sources": [source],
                })

        # Normalize-then-dedup by canonical gene symbol, including against existing stage_3.
        seen: set[str] = {
            (t.get("gene_symbol") or "").upper() for t in existing_targets_full
        }
        deduped_new: list[dict] = []
        dedup_labels: list[str] = []
        for t in lenient_targets:
            sym = (t["gene_symbol"] or "").upper()
            if not sym or sym in seen:
                if sym:
                    dedup_labels.append(t["gene_symbol"])
                continue
            seen.add(sym)
            deduped_new.append(t)

        all_targets = existing_targets_full + deduped_new
        stage3_result = {
            "target_count": len(all_targets),
            "target_ids": [t["target_id"] for t in all_targets],
            "target_gene_symbols": [t["gene_symbol"] for t in all_targets],
            "target_compound_map": {t["gene_symbol"]: [] for t in all_targets},
            "targets": all_targets,
            "covered": len(all_targets),
            "no_data": 0,
            "coverage_pct": 100.0,
            "compound_sources": {},
            "uncovered_compounds": [],
        }
        await analysis_repo.update_run_status(
            session, analysis_id, status=run.status, stage_results={"stage_3": stage3_result},
        )
        await analysis_repo.merge_run_parameters(session, analysis_id, {"_input_mode": "manual_targets"})

        # Accession-resolved targets carry a UniProt accession — persist them (symbol-only
        # targets have uniprot_id=None and are skipped by the persist service).
        cached = await persist_validated_targets(deduped_new, session)

        return InjectTargetsResponse(
            injected=len(deduped_new),
            failed=[],
            duplicates_removed=len(dedup_labels),
            duplicate_names=dedup_labels,
            cached=cached,
            normalized=normalized_changes,
            unrecognized=unrecognized,
        )

    # Validate each deduplicated target via UniProt
    async def _validate_one(entry: dict) -> tuple[dict | None, str | None]:
        """Validate one target entry. Returns (target_dict, error_label) — one is None."""
        raw = entry.get("_raw", entry.get("gene_symbol") or entry.get("uniprot_id") or "")
        raw_stripped = raw.strip() if isinstance(raw, str) else ""
        if not raw_stripped:
            return None, raw
        is_accession = bool(_UNIPROT_ACCESSION_RE.match(raw_stripped))
        try:
            info = await validate_human_target(
                gene_symbol=None if is_accession else raw_stripped,
                uniprot_id=raw_stripped if is_accession else None,
            )
        except ServiceUnavailableError:
            raise  # propagate to inject_targets endpoint → 503
        except ValueError:
            return None, raw_stripped

        target_id = _make_target_id(info.uniprot_accession, info.gene_symbol)
        return {
            "target_id": target_id,
            "gene_symbol": info.gene_symbol,
            "uniprot_id": info.uniprot_accession,
            "protein_name": info.protein_name,
            "target_score": 1.0,
            "compound_ids": [],
            "sources": ["manual"],
        }, None

    injected_targets: list[dict] = []
    failed: list[str] = []
    try:
        results = await asyncio.gather(*[_validate_one(e) for e in deduped_dicts])
        for target, error in results:
            if target:
                injected_targets.append(target)
            elif error:
                failed.append(error)
    except ServiceUnavailableError as exc:
        logger.error("UniProt unavailable during inject-targets: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=UNIPROT_UNAVAILABLE)

    if not injected_targets:
        return InjectTargetsResponse(
            injected=0,
            failed=failed,
            duplicates_removed=len(dedup_removed_labels),
            duplicate_names=dedup_removed_labels,
        )

    # Secondary dedup by UniProt accession (catches any remaining gene_symbol collisions
    # not resolved in the pre-validation pass — e.g. two different gene symbols that
    # resolve to the same protein).
    seen_accessions: set[str] = set()
    final_targets: list[dict] = []
    # Build map of original user inputs for dedup tracking
    original_inputs: dict[str, str] = {}
    for e in deduped_dicts:
        raw = e.get("_raw", e.get("gene_symbol") or e.get("uniprot_id") or "")
        if e.get("uniprot_id"):
            original_inputs[e["uniprot_id"].upper()] = raw
        elif e.get("gene_symbol"):
            original_inputs[e["gene_symbol"].upper()] = raw

    for t in injected_targets:
        acc = t["uniprot_id"].upper()
        if acc not in seen_accessions:
            seen_accessions.add(acc)
            final_targets.append(t)
        else:
            # Track original user input, not just gene_symbol
            user_input = original_inputs.get(acc, t["gene_symbol"])
            dedup_removed_labels.append(user_input)

    new_targets = [
        {k: v for k, v in t.items() if k != "target_score"}
        for t in final_targets
    ]

    # Merge with existing stage_3 targets so repeated batch calls accumulate
    all_targets = existing_targets_full + new_targets

    # Build synthetic stage_3 result — stage 5 reads target_gene_symbols
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

    # Persist the newly validated targets to the canonical targets table,
    # mirroring compound persistence on inject-compounds. Only targets with a UniProt
    # accession are stored; failures are non-fatal and return 0.
    from app.services.target_persist import persist_validated_targets
    cached = await persist_validated_targets(new_targets, session)

    return InjectTargetsResponse(
        injected=len(new_targets),
        failed=failed,
        duplicates_removed=len(dedup_removed_labels),
        duplicate_names=dedup_removed_labels,
        cached=cached,
    )
