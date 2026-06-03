import copy
import csv
import io
import json
import logging
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session, async_session_factory
from app.errors import (
    PUBCHEM_UNAVAILABLE,
    UNIPROT_UNAVAILABLE,
    UNIPROT_TARGET_NOT_FOUND,
    UNIPROT_VALIDATION_FAILED,
    TARGET_NOT_FOUND,
    TARGET_ALREADY_EXISTS,
)
from app.schemas.analysis import (
    CreateAnalysisRequest, AnalysisStatusResponse, AnalysisRunResponse,
    ResetFromRequest, ApproveRequest,
    AddUserTargetRequest, AddUserTargetResponse,
    AddUserCompoundRequest, AddUserCompoundResponse,
)
from app.schemas.import_targets import ImportTargetsRequest, ImportTargetsResponse, STPTarget
from app.models.target import Target, CompoundTarget
from app.repositories import analysis_repo
from analysis.pipeline import run_stage
from analysis.stages.stage3_targets import _make_target_id
from app.services.canonicalize import make_target_id, make_compound_target_id, target_canonical_key
from app.services.target_persist import persist_canonical_target
from integrations.uniprot import validate_human_target
from integrations._retry import ServiceUnavailableError

router = APIRouter(prefix="/analyses", tags=["analyses"])
logger = logging.getLogger(__name__)


def _stage6_csv(stage_data: dict) -> tuple[list[str], list[dict]]:
    """Stage 6 PPI edges → flat CSV rows. Reads the flat raw_edges (not Cytoscape-nested edges)."""
    fieldnames = ["source", "target", "combined_score"]
    rows = [
        {
            "source": e.get("source", ""),
            "target": e.get("target", ""),
            "combined_score": e.get("combined_score", ""),
        }
        for e in stage_data.get("raw_edges", [])
    ]
    return fieldnames, rows


def _stage2_csv(stage_data: dict) -> tuple[list[str], list[dict]]:
    """Stage 2 ADME → one row per compound (all statuses) with property columns."""
    fieldnames = [
        "compound_id", "canonical_name", "status",
        "molecular_weight", "logp", "tpsa",
        "hbond_donors", "hbond_acceptors",
        "np_likeness_score", "rotatable_bonds", "is_pains_positive",
    ]
    rows = [
        {
            "compound_id": c.get("compound_id", ""),
            "canonical_name": c.get("canonical_name", ""),
            "status": c.get("status", ""),
            "molecular_weight": c.get("molecular_weight", ""),
            "logp": c.get("logp", ""),
            "tpsa": c.get("tpsa", ""),
            "hbond_donors": c.get("hbond_donors", ""),
            "hbond_acceptors": c.get("hbond_acceptors", ""),
            "np_likeness_score": c.get("np_likeness_score", ""),
            "rotatable_bonds": c.get("rotatable_bonds", ""),
            "is_pains_positive": c.get("is_pains_positive", ""),
        }
        for c in stage_data.get("compounds", [])
    ]
    return fieldnames, rows

TOTAL_STAGES = 8


def _status_to_done(status: str) -> int:
    if status == "complete":
        return TOTAL_STAGES
    if status.startswith("stage_"):
        try:
            return int(status.split("_")[1]) - 1
        except (IndexError, ValueError):
            return 0
    return 0


@router.post("", response_model=AnalysisStatusResponse, status_code=201)
async def create_analysis(
    body: CreateAnalysisRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    from analysis.pipeline import start_pipeline  # imported here to avoid a circular import at module load
    from app.services.manual_inputs import inject_compounds_service, inject_targets_service

    # plant_ids is intentionally allowed to be empty here: manual_compounds and
    # manual_targets modes send an empty list because stage 1 is skipped.
    # The frontend Zod schema enforces plant_ids ≥ 1 for standard mode before submit.
    #
    # Control state is derived server-side from the input fields and written into the
    # STORED parameters; the inbound `parameters` payload is pure pipeline config.
    # Compounds/targets injection sets `_input_mode` via the services below; the
    # disease-side keys have no service, so we write them here directly.
    input_mode = (
        "manual_compounds" if body.compounds
        else "manual_targets" if body.targets
        else "standard"
    )
    parameters: dict = {
        **body.parameters.model_dump(exclude_none=True),
        "_plant_ids": [str(pid) for pid in body.plant_ids],
        "_disease_id": str(body.disease_id) if body.disease_id else None,
    }
    if input_mode != "standard":
        parameters["_input_mode"] = input_mode
    if body.manual_disease_targets:
        parameters["_disease_input_mode"] = "manual_targets"
        parameters["_injected_disease_targets"] = body.manual_disease_targets

    run = await analysis_repo.create_run(
        session, body.name, body.mode, parameters,
        disease_id=body.disease_id,
    )

    # Inject manual inputs synchronously BEFORE scheduling the pipeline (atomic
    # create-with-inputs — closes the old create → schedule → inject 409 race). If
    # injection fails (all inputs invalid, or PubChem/UniProt unreachable), roll the
    # create back so no orphan 'pending' run is left behind.
    try:
        if body.compounds:
            result = await inject_compounds_service(body.compounds, run, session)
            if result.injected == 0:
                raise HTTPException(status_code=422, detail="No valid compounds could be injected")
        if body.targets:
            result = await inject_targets_service(body.targets, False, run, session)
            if result.injected == 0:
                raise HTTPException(status_code=422, detail="No valid targets could be injected")
    except HTTPException:
        await analysis_repo.delete_run(session, run.analysis_id)
        raise

    background_tasks.add_task(
        start_pipeline, run.analysis_id, body.plant_ids, body.disease_id, async_session_factory
    )
    return AnalysisStatusResponse(
        analysis_id=run.analysis_id,
        status=run.status,
        mode=run.mode,
        current_stage=run.current_stage,
        progress={"done": 0, "total": TOTAL_STAGES},
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("", response_model=list[AnalysisRunResponse])
async def list_analyses(session: AsyncSession = Depends(get_session)):
    runs = await analysis_repo.list_runs(session)
    return [AnalysisRunResponse(**r.model_dump()) for r in runs]


@router.get("/{analysis_id}/status", response_model=AnalysisStatusResponse)
async def get_status(analysis_id: UUID, session: AsyncSession = Depends(get_session)):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisStatusResponse(
        analysis_id=run.analysis_id,
        status=run.status,
        mode=run.mode,
        current_stage=run.current_stage,
        progress={"done": _status_to_done(run.status), "total": TOTAL_STAGES},
        created_at=run.created_at,
        updated_at=run.updated_at,
        error_message=run.error_message,
        expires_at=run.expires_at,
    )


@router.get("/{analysis_id}", response_model=AnalysisRunResponse)
async def get_analysis(analysis_id: UUID, session: AsyncSession = Depends(get_session)):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if run.expires_at and run.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Analysis has expired")
    return AnalysisRunResponse(**run.model_dump())


@router.post("/{analysis_id}/approve")
async def approve_stage(
    analysis_id: UUID,
    background_tasks: BackgroundTasks,
    body: ApproveRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    run = await analysis_repo.get_run_locked(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if "_awaiting_approval" not in run.status:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis is not awaiting approval (current status: {run.status})"
        )

    current_stage = int(run.status.split("_")[1])
    next_stage = current_stage + 1

    # Apply param overrides for next stage before running it
    if body and body.param_overrides:
        await analysis_repo.merge_run_parameters(session, analysis_id, body.param_overrides)

    if next_stage > 8:
        await analysis_repo.update_run_status(
            session, analysis_id, status="complete", completed=True
        )
        return {"status": "complete"}

    background_tasks.add_task(
        run_stage, analysis_id, next_stage, async_session_factory
    )
    return {"status": f"stage_{next_stage}_starting", "next_stage": next_stage}


@router.post("/{analysis_id}/reject")
async def reject_stage(
    analysis_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    run = await analysis_repo.get_run_locked(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if "_awaiting_approval" not in run.status:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis is not awaiting approval (current status: {run.status})"
        )

    current_stage = int(run.status.split("_")[1])
    await analysis_repo.update_run_status(
        session, analysis_id,
        status=f"stage_{current_stage}_rejected",
    )
    return {"status": f"stage_{current_stage}_rejected"}


@router.post("/{analysis_id}/reset-from/{stage}", response_model=AnalysisStatusResponse)
async def reset_from_stage(
    analysis_id: UUID,
    stage: int,
    background_tasks: BackgroundTasks,
    body: ResetFromRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Clear stage results from `stage` onward and reset to previous approval state.

    Optional body:
    - params: dict of PipelineConfig param overrides (e.g. {"adme": {"max_mw": 600}})
    - rerun: if True, immediately starts running the stage (stage > 1 only)

    After reset:
    - stage > 1: status becomes ``stage_{stage-1}_awaiting_approval``
    - stage == 1: pipeline restarts from the beginning (auto-triggered)
    """
    from analysis.pipeline import start_pipeline
    if stage < 1 or stage > TOTAL_STAGES:
        raise HTTPException(
            status_code=422,
            detail=f"stage must be between 1 and {TOTAL_STAGES}",
        )
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    param_overrides = body.params if body else None
    run = await analysis_repo.reset_run_from_stage(session, analysis_id, stage, param_overrides)

    if stage == 1:
        plant_ids = (run.parameters or {}).get("_plant_ids", [])
        disease_id = (run.parameters or {}).get("_disease_id")
        background_tasks.add_task(
            start_pipeline, run.analysis_id, plant_ids, disease_id, async_session_factory
        )
    elif body and body.rerun:
        background_tasks.add_task(run_stage, analysis_id, stage, async_session_factory)

    return AnalysisStatusResponse(
        analysis_id=run.analysis_id,
        status=run.status,
        mode=run.mode,
        current_stage=run.current_stage,
        progress={"done": _status_to_done(run.status), "total": TOTAL_STAGES},
        created_at=run.created_at,
        updated_at=run.updated_at,
        expires_at=run.expires_at,
    )


@router.delete("/{analysis_id}")
async def delete_analysis(analysis_id: UUID, session: AsyncSession = Depends(get_session)):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    await session.delete(run)
    await session.commit()
    return {"deleted": True}


@router.get("/{analysis_id}/export/{stage}")
async def export_stage_results(
    analysis_id: UUID,
    stage: str,
    format: str = "json",  # 'json' | 'csv'
    session: AsyncSession = Depends(get_session),
):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stage_key = f"stage_{stage}" if not stage.startswith("stage_") else stage
    stage_data = (run.stage_results or {}).get(stage_key)
    if stage_data is None:
        raise HTTPException(status_code=404, detail=f"Stage {stage} results not found")

    if format == "json":
        content = json.dumps(stage_data, indent=2)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={run.analysis_name}_{stage_key}.json"},
        )

    # CSV: flatten stage data into a tabular representation
    if format == "csv":
        output = io.StringIO()

        if stage_key == "stage_1":
            # One row per compound_id
            compound_ids = stage_data.get("compound_ids", [])
            writer = csv.DictWriter(output, fieldnames=["compound_id"])
            writer.writeheader()
            for cid in compound_ids:
                writer.writerow({"compound_id": cid})
            filename = f"{run.analysis_name}_stage1_compounds.csv"

        elif stage_key == "stage_2":
            fieldnames, rows = _stage2_csv(stage_data)
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            filename = f"{run.analysis_name}_stage2_adme.csv"

        elif stage_key == "stage_3":
            # One row per target — gene_symbol, compound_count, compound_ids (joined)
            target_compound_map = stage_data.get("target_compound_map", {})
            fieldnames = ["gene_symbol", "compound_count", "compound_ids"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for gene, cids in target_compound_map.items():
                writer.writerow({
                    "gene_symbol": gene,
                    "compound_count": len(cids),
                    "compound_ids": "|".join(cids),
                })
            filename = f"{run.analysis_name}_stage3_targets.csv"

        elif stage_key == "stage_4":
            # One row per disease target
            targets = stage_data.get("targets", [])
            if targets:
                fieldnames = ["gene_symbol", "uniprot_accession", "score", "source"]
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for t in targets:
                    writer.writerow({
                        "gene_symbol": t.get("gene_symbol", ""),
                        "uniprot_accession": t.get("uniprot_accession", ""),
                        "score": t.get("score", ""),
                        "source": t.get("source", ""),
                    })
            else:
                writer = csv.DictWriter(output, fieldnames=["gene_symbol", "uniprot_accession", "score", "source"])
                writer.writeheader()
            filename = f"{run.analysis_name}_stage4_disease_targets.csv"

        elif stage_key == "stage_5":
            # Overlap gene list rows plus a summary stats block
            overlap_genes = stage_data.get("overlap", [])
            fieldnames = ["type", "value"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow({"type": "overlap_count", "value": stage_data.get("overlap_count", 0)})
            writer.writerow({"type": "compound_only_count", "value": stage_data.get("compound_only_count", 0)})
            writer.writerow({"type": "disease_only_count", "value": stage_data.get("disease_only_count", 0)})
            writer.writerow({"type": "jaccard", "value": stage_data.get("jaccard", 0)})
            writer.writerow({"type": "p_value", "value": stage_data.get("p_value", "")})
            writer.writerow({"type": "significant", "value": stage_data.get("significant", "")})
            for gene in overlap_genes:
                writer.writerow({"type": "overlap_gene", "value": gene})
            filename = f"{run.analysis_name}_stage5_overlap.csv"

        elif stage_key == "stage_6":
            fieldnames, rows = _stage6_csv(stage_data)
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            filename = f"{run.analysis_name}_stage6_ppi_edges.csv"

        elif stage_key == "stage_7":
            rows = stage_data.get("ranked", [])
            if rows:
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            else:
                writer = csv.DictWriter(output, fieldnames=["gene_symbol", "degree", "betweenness", "closeness", "eigenvector", "is_hub", "is_hub_bottleneck", "rank"])
                writer.writeheader()
            filename = f"{run.analysis_name}_stage7_hub_genes.csv"

        elif stage_key == "stage_8":
            # One row per pathway term across all sources
            fieldnames = ["source", "term_id", "term_name", "p_value", "fdr", "intersection_size", "term_size", "genes"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for source_key, source_label in [("go_bp", "GO:BP"), ("go_mf", "GO:MF"), ("go_cc", "GO:CC"), ("kegg", "KEGG")]:
                for term in stage_data.get(source_key, []):
                    writer.writerow({
                        "source": source_label,
                        "term_id": term.get("term_id", ""),
                        "term_name": term.get("term_name", ""),
                        "p_value": term.get("p_value", ""),
                        "fdr": term.get("fdr", ""),
                        "intersection_size": term.get("intersection_size", ""),
                        "term_size": term.get("term_size", ""),
                        "genes": "|".join(term.get("genes", [])),
                    })
            filename = f"{run.analysis_name}_stage8_enrichment.csv"

        else:
            # Unknown stage — fall back to JSON with a comment header
            content = f"# CSV not available for {stage_key}; returning JSON\n" + json.dumps(stage_data, indent=2)
            return StreamingResponse(
                io.StringIO(content),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={run.analysis_name}_{stage_key}.json"},
            )

        output.seek(0)
        safe_filename = filename.encode("ascii", "replace").decode("ascii").replace("?", "_")
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={safe_filename}"},
        )

    # Default: return JSON
    content = json.dumps(stage_data, indent=2)
    return StreamingResponse(
        io.StringIO(content),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={run.analysis_name}_{stage_key}.json"},
    )


def _merge_stp_targets(stage3: dict, compound_id: str, new_targets: list[STPTarget]) -> dict:
    """Merge STP-imported targets into a Stage 3 result dict.

    Preserves all existing ChEMBL/PubChem targets. Adds new STP targets tagged
    as 'user_provided'. Updates coverage stats and removes the compound from the
    uncovered_compounds list if it had zero targets before.
    """
    result = copy.deepcopy(stage3)

    was_uncovered = any(
        c["compound_id"] == compound_id
        for c in result.get("uncovered_compounds", [])
    )

    # Index existing targets by gene symbol for fast lookup
    gene_to_target: dict[str, dict] = {
        t["gene_symbol"].upper(): t for t in result.get("targets", [])
    }

    for stp_t in new_targets:
        gene = stp_t.gene_symbol.upper()
        if not gene:
            continue
        if gene in gene_to_target:
            # Extend existing target with this compound
            et = gene_to_target[gene]
            if compound_id not in et["compound_ids"]:
                et["compound_ids"].append(compound_id)
                et["compound_count"] = len(et["compound_ids"])
        else:
            # New target from STP
            new_t: dict = {
                "gene_symbol": gene,
                "uniprot_id": stp_t.uniprot_id,
                "compound_count": 1,
                "compound_ids": [compound_id],
                "source": "user_provided",
            }
            result.setdefault("targets", []).append(new_t)
            gene_to_target[gene] = new_t

    # Update compound_sources (only when new targets were actually provided)
    if new_targets:
        sources: dict[str, list[str]] = result.get("compound_sources", {})
        compound_srcs = list(sources.get(compound_id, []))
        if "user_provided" not in compound_srcs:
            compound_srcs.append("user_provided")
        sources[compound_id] = compound_srcs
        result["compound_sources"] = sources

    # Update pipeline chain keys
    result["target_count"] = len(result.get("targets", []))
    result["target_gene_symbols"] = [t["gene_symbol"] for t in result.get("targets", [])]
    result["target_compound_map"] = {
        t["gene_symbol"]: t["compound_ids"] for t in result.get("targets", [])
    }

    # Only transition compound from uncovered→covered if new targets were actually added
    if was_uncovered and new_targets:
        result["covered"] = result.get("covered", 0) + 1
        result["no_data"] = max(0, result.get("no_data", 0) - 1)
        result["uncovered_compounds"] = [
            c for c in result.get("uncovered_compounds", [])
            if c["compound_id"] != compound_id
        ]
    elif not was_uncovered:
        # Already covered — remove any stale entry if somehow present
        result["uncovered_compounds"] = [
            c for c in result.get("uncovered_compounds", [])
            if c["compound_id"] != compound_id
        ]
    # If was_uncovered but new_targets is empty: leave uncovered_compounds and stats as-is

    total = result.get("covered", 0) + len(result["uncovered_compounds"])
    result["coverage_pct"] = round(result["covered"] / total * 100, 1) if total else 0.0

    return result


def _add_target_to_stage3(
    stage3: dict,
    gene_symbol: str,
    uniprot_id: str | None,
    protein_name: str | None,
) -> dict:
    """Inject a user-provided target into a stage_3 result dict (deep copy — no mutation)."""
    result = copy.deepcopy(stage3)
    existing_genes = {t["gene_symbol"].upper() for t in result.get("targets", [])}
    if gene_symbol.upper() in existing_genes:
        raise ValueError(f"Target {gene_symbol} already in Stage 3 results")
    result.setdefault("targets", []).append({
        "gene_symbol": gene_symbol,
        "uniprot_id": uniprot_id or "",
        "protein_name": protein_name,
        "compound_count": 0,
        "compound_ids": [],
        "source": "user_provided",
    })
    result["target_count"] = len(result["targets"])
    result.setdefault("target_gene_symbols", []).append(gene_symbol)
    result["user_modified"] = True
    return result


def _remove_target_from_stage3(stage3: dict, gene_symbol: str) -> dict:
    """Remove a target from a stage_3 result dict by gene_symbol (deep copy — no mutation)."""
    result = copy.deepcopy(stage3)
    targets = result.get("targets", [])
    new_targets = [t for t in targets if t["gene_symbol"].upper() != gene_symbol.upper()]
    if len(new_targets) == len(targets):
        raise KeyError(f"Target {gene_symbol} not found in Stage 3 results")
    result["targets"] = new_targets
    result["target_count"] = len(new_targets)
    result["target_gene_symbols"] = [t["gene_symbol"] for t in new_targets]
    result["user_modified"] = True
    return result


def _add_target_to_stage4(
    stage4: dict,
    gene_symbol: str,
    uniprot_id: str | None,
    protein_name: str | None,
) -> dict:
    """Inject a user-provided target into a stage_4 result dict (deep copy — no mutation)."""
    result = copy.deepcopy(stage4)
    existing_genes = {t["gene_symbol"].upper() for t in result.get("targets", [])}
    if gene_symbol.upper() in existing_genes:
        raise ValueError(f"Target {gene_symbol} already in Stage 4 results")
    result.setdefault("targets", []).append({
        "gene_symbol": gene_symbol,
        "uniprot_accession": uniprot_id or "",
        "protein_name": protein_name,
        "score": 1.0,
        "source": "user_provided",
    })
    result["disease_target_count"] = len(result["targets"])
    result.setdefault("disease_gene_symbols", []).append(gene_symbol)
    result["user_modified"] = True
    return result


def _remove_target_from_stage4(stage4: dict, gene_symbol: str) -> dict:
    """Remove a target from a stage_4 result dict by gene_symbol (deep copy — no mutation)."""
    result = copy.deepcopy(stage4)
    targets = result.get("targets", [])
    new_targets = [t for t in targets if t["gene_symbol"].upper() != gene_symbol.upper()]
    if len(new_targets) == len(targets):
        raise KeyError(f"Target {gene_symbol} not found in Stage 4 results")
    result["targets"] = new_targets
    result["disease_target_count"] = len(new_targets)
    result["disease_gene_symbols"] = [t["gene_symbol"] for t in new_targets]
    result["user_modified"] = True
    return result


@router.post("/{analysis_id}/import-targets", response_model=ImportTargetsResponse)
async def import_targets(
    analysis_id: UUID,
    body: ImportTargetsRequest,
    session: AsyncSession = Depends(get_session),
):
    """Import SwissTargetPrediction results for one compound into Stage 3."""
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stage3 = (run.stage_results or {}).get("stage_3")
    if not stage3:
        raise HTTPException(status_code=400, detail="Stage 3 results not available")

    # Validate compound belongs to this analysis
    all_compound_ids: list[str] = (run.stage_results.get("stage_2") or {}).get(
        "all_active_compound_ids", []
    )
    if body.compound_id not in all_compound_ids:
        raise HTTPException(
            status_code=422, detail=f"compound_id {body.compound_id!r} not found in this analysis"
        )

    now = datetime.utcnow()
    imported = 0
    skipped = 0

    try:
        for stp_t in body.targets:
            target_id = make_target_id(stp_t.uniprot_id)

            # Upsert Target row (insert-if-absent; no commit — see commit below)
            await persist_canonical_target([Target(
                target_id=target_id,
                canonical_key=target_canonical_key(stp_t.uniprot_id),
                gene_symbol=stp_t.gene_symbol.upper(),
                uniprot_accession=stp_t.uniprot_id,
                retrieved_at=now,
            )], session)

            # Upsert CompoundTarget row
            ct_id = make_compound_target_id(body.compound_id, target_id)
            existing_ct = (await session.exec(
                select(CompoundTarget).where(CompoundTarget.compound_target_id == ct_id)
            )).one_or_none()
            if existing_ct is None:
                session.add(CompoundTarget(
                    compound_target_id=ct_id,
                    compound_id=body.compound_id,
                    target_id=target_id,
                    prediction_method="stp_import",
                    pchembl_value=None,
                    retrieved_at=now,
                ))
                imported += 1
            else:
                skipped += 1

        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Conflict: one or more targets already exist")

    # Re-aggregate Stage 3 results and persist
    updated_stage3 = _merge_stp_targets(stage3, body.compound_id, body.targets)
    await analysis_repo.update_run_status(
        session, analysis_id,
        status=run.status,
        stage_results={"stage_3": updated_stage3},
    )

    return ImportTargetsResponse(imported=imported, skipped=skipped)


@router.post("/{analysis_id}/user-compounds", response_model=AddUserCompoundResponse, status_code=200)
async def add_user_compound(
    analysis_id: UUID,
    body: AddUserCompoundRequest,
    session: AsyncSession = Depends(get_session),
):
    """Add a single compound to Stage 1 results (post-fetch curation). Validates via PubChem."""
    import httpx
    from integrations.pubchem_compound import validate_compound

    run = await analysis_repo.get_run_locked(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stage1 = (run.stage_results or {}).get("stage_1")
    if not stage1:
        raise HTTPException(status_code=400, detail="Stage 1 results not available")

    structure = body.smiles or body.inchi
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            validated = await validate_compound(structure, client)
        except ServiceUnavailableError as e:
            logger.error("PubChem compound validation error: %s", e, exc_info=True)
            raise HTTPException(status_code=503, detail=PUBCHEM_UNAVAILABLE)
        except Exception as e:
            logger.error("PubChem compound validation error: %s", e, exc_info=True)
            raise HTTPException(status_code=502, detail=PUBCHEM_UNAVAILABLE)

    if not validated:
        raise HTTPException(status_code=400, detail="Invalid compound structure: not found in PubChem")

    # Populate smiles from request body (PubChem does not return canonical SMILES
    # via the property endpoint we use, so fall back to what the user provided).
    if body.smiles:
        validated["smiles"] = body.smiles

    # Merge into stage_1 compounds (stage1 guard already confirmed it exists above)
    stage1 = dict(stage1)
    existing_ids = {c["compound_id"] for c in stage1.get("compounds", [])}
    if validated["compound_id"] not in existing_ids:
        stage1.setdefault("compounds", []).append({
            "compound_id": validated["compound_id"],
            "canonical_name": validated["canonical_name"],
            "plant_ids": [],
        })
    stage1["compound_ids"] = [c["compound_id"] for c in stage1["compounds"]]
    stage1["total_compounds"] = len(stage1["compounds"])
    stage1["compound_count"] = len(stage1["compounds"])
    stage1["user_modified"] = True

    await analysis_repo.update_run_status(
        session, analysis_id,
        status=run.status,
        stage_results={"stage_1": stage1},
    )
    return AddUserCompoundResponse(
        compound_id=validated["compound_id"],
        canonical_name=validated["canonical_name"],
        smiles=validated.get("smiles"),
    )


@router.delete("/{analysis_id}/user-compounds/{compound_id}", status_code=200)
async def remove_user_compound(
    analysis_id: UUID,
    compound_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Remove a compound from Stage 1 results by compound_id."""
    run = await analysis_repo.get_run_locked(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stage1_raw = (run.stage_results or {}).get("stage_1")
    if not stage1_raw:
        raise HTTPException(status_code=400, detail="Stage 1 results not available")

    stage1 = dict(stage1_raw)
    compounds_before = stage1.get("compounds", [])
    filtered = [c for c in compounds_before if c["compound_id"] != compound_id]
    if len(filtered) == len(compounds_before):
        raise HTTPException(status_code=404, detail="Compound not found in stage 1 results")
    stage1["compounds"] = filtered
    stage1["compound_ids"] = [c["compound_id"] for c in stage1["compounds"]]
    stage1["total_compounds"] = len(stage1["compounds"])
    stage1["compound_count"] = len(stage1["compounds"])
    stage1["user_modified"] = True

    await analysis_repo.update_run_status(
        session, analysis_id,
        status=run.status,
        stage_results={"stage_1": stage1},
    )
    return {"removed": compound_id}


@router.post("/{analysis_id}/targets/user", response_model=AddUserTargetResponse, status_code=201)
async def add_user_target(
    analysis_id: UUID,
    body: AddUserTargetRequest,
    session: AsyncSession = Depends(get_session),
):
    """Add a user-provided target to Stage 3 results. Validates via UniProt."""
    run = await analysis_repo.get_run_locked(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    stage3 = (run.stage_results or {}).get("stage_3")
    if not stage3:
        raise HTTPException(status_code=400, detail="Stage 3 results not available")

    try:
        info = await validate_human_target(body.gene_symbol, body.uniprot_id)
    except ServiceUnavailableError as exc:
        logger.error("UniProt target validation error: %s", exc)
        raise HTTPException(status_code=503, detail=UNIPROT_UNAVAILABLE)
    except ValueError as exc:
        msg = str(exc)
        logger.error("UniProt target validation error: %s", msg)
        if "request failed" in msg or "returned error" in msg or "invalid JSON" in msg:
            raise HTTPException(status_code=502, detail=UNIPROT_UNAVAILABLE)
        if "not found" in msg or "not a human protein" in msg:
            raise HTTPException(status_code=422, detail=UNIPROT_TARGET_NOT_FOUND)
        raise HTTPException(status_code=422, detail=UNIPROT_VALIDATION_FAILED)

    # Upsert Target row (canonical cache — permanent)
    target_id = _make_target_id(info.uniprot_accession, info.gene_symbol)
    await persist_canonical_target([Target(
        target_id=target_id,
        canonical_key=f"uniprot:{info.uniprot_accession}",
        gene_symbol=info.gene_symbol,
        uniprot_accession=info.uniprot_accession,
        protein_name=info.protein_name,
        retrieved_at=datetime.utcnow(),
    )], session)

    try:
        updated = _add_target_to_stage3(stage3, info.gene_symbol, info.uniprot_accession, info.protein_name)
    except ValueError as exc:
        logger.warning("Duplicate target rejected for stage 3: %s", exc)
        raise HTTPException(status_code=409, detail=TARGET_ALREADY_EXISTS)

    await session.commit()
    await analysis_repo.update_run_status(
        session, analysis_id,
        status=run.status,
        stage_results={"stage_3": updated},
    )
    return AddUserTargetResponse(
        target_id=target_id,
        gene_symbol=info.gene_symbol,
        uniprot_id=info.uniprot_accession,
        protein_name=info.protein_name,
    )


@router.delete("/{analysis_id}/targets/{gene_symbol}", status_code=204)
async def remove_user_target(
    analysis_id: UUID,
    gene_symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Remove any target from Stage 3 results by gene symbol."""
    run = await analysis_repo.get_run_locked(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    stage3 = (run.stage_results or {}).get("stage_3")
    if not stage3:
        raise HTTPException(status_code=400, detail="Stage 3 results not available")

    try:
        updated = _remove_target_from_stage3(stage3, gene_symbol)
    except KeyError as exc:
        logger.warning("Target removal rejected for stage 3: %s", exc)
        raise HTTPException(status_code=404, detail=TARGET_NOT_FOUND)

    await analysis_repo.update_run_status(
        session, analysis_id,
        status=run.status,
        stage_results={"stage_3": updated},
    )
    return None


@router.post("/{analysis_id}/disease-targets/user", response_model=AddUserTargetResponse, status_code=201)
async def add_user_disease_target(
    analysis_id: UUID,
    body: AddUserTargetRequest,
    session: AsyncSession = Depends(get_session),
):
    """Add a user-provided target to Stage 4 (disease targets) results. Validates via UniProt."""
    run = await analysis_repo.get_run_locked(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    stage4 = (run.stage_results or {}).get("stage_4")
    if not stage4:
        raise HTTPException(status_code=400, detail="Stage 4 results not available")

    try:
        info = await validate_human_target(body.gene_symbol, body.uniprot_id)
    except ServiceUnavailableError as exc:
        logger.error("UniProt disease-target validation error: %s", exc)
        raise HTTPException(status_code=503, detail=UNIPROT_UNAVAILABLE)
    except ValueError as exc:
        msg = str(exc)
        logger.error("UniProt disease-target validation error: %s", msg)
        if "request failed" in msg or "returned error" in msg or "invalid JSON" in msg:
            raise HTTPException(status_code=502, detail=UNIPROT_UNAVAILABLE)
        if "not found" in msg or "not a human protein" in msg:
            raise HTTPException(status_code=422, detail=UNIPROT_TARGET_NOT_FOUND)
        raise HTTPException(status_code=422, detail=UNIPROT_VALIDATION_FAILED)

    # Upsert Target row (canonical cache — permanent)
    target_id = _make_target_id(info.uniprot_accession, info.gene_symbol)
    await persist_canonical_target([Target(
        target_id=target_id,
        canonical_key=f"uniprot:{info.uniprot_accession}",
        gene_symbol=info.gene_symbol,
        uniprot_accession=info.uniprot_accession,
        protein_name=info.protein_name,
        retrieved_at=datetime.utcnow(),
    )], session)

    try:
        updated = _add_target_to_stage4(
            stage4, info.gene_symbol, info.uniprot_accession, info.protein_name
        )
    except ValueError as exc:
        logger.warning("Duplicate target rejected for stage 4: %s", exc)
        raise HTTPException(status_code=409, detail=TARGET_ALREADY_EXISTS)

    await session.commit()
    await analysis_repo.update_run_status(
        session, analysis_id,
        status=run.status,
        stage_results={"stage_4": updated},
    )
    return AddUserTargetResponse(
        target_id=target_id,
        gene_symbol=info.gene_symbol,
        uniprot_id=info.uniprot_accession,
        protein_name=info.protein_name,
    )


@router.delete("/{analysis_id}/disease-targets/{gene_symbol}", status_code=204)
async def remove_user_disease_target(
    analysis_id: UUID,
    gene_symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Remove any target from Stage 4 results by gene symbol."""
    run = await analysis_repo.get_run_locked(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    stage4 = (run.stage_results or {}).get("stage_4")
    if not stage4:
        raise HTTPException(status_code=400, detail="Stage 4 results not available")

    try:
        updated = _remove_target_from_stage4(stage4, gene_symbol)
    except KeyError as exc:
        logger.warning("Target removal rejected for stage 4: %s", exc)
        raise HTTPException(status_code=404, detail=TARGET_NOT_FOUND)

    await analysis_repo.update_run_status(
        session, analysis_id,
        status=run.status,
        stage_results={"stage_4": updated},
    )
    return None
