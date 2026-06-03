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
    InjectCompoundsRequest, InjectCompoundsResponse,
    InjectTargetsRequest, InjectTargetsResponse,
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
    # plant_ids is intentionally allowed to be empty here: manual_compounds and
    # manual_targets modes send an empty list because stage 1 is skipped.
    # _input_mode is set later by inject-compounds / inject-targets endpoints,
    # so we cannot enforce plant_ids ≥ 1 at the schema level for standard mode.
    # The frontend Zod schema enforces plant_ids ≥ 1 for standard mode before submit.
    parameters = {
        **body.parameters.model_dump(exclude_none=True),
        "_plant_ids": [str(pid) for pid in body.plant_ids],
        "_disease_id": str(body.disease_id) if body.disease_id else None,
    }
    run = await analysis_repo.create_run(
        session, body.name, body.mode, parameters,
        disease_id=body.disease_id,
    )
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
    run = await analysis_repo.get_run(session, analysis_id)
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
    run = await analysis_repo.get_run(session, analysis_id)
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


@router.post("/{analysis_id}/inject-compounds", response_model=InjectCompoundsResponse, status_code=200)
async def inject_compounds(
    analysis_id: UUID,
    body: InjectCompoundsRequest,
    session: AsyncSession = Depends(get_session),
):
    """Validate SMILES/InChI strings via PubChem and inject as stage 1+2 results.

    Enables manual compound input mode (T4.3): stage 3 will read the injected
    compounds from stage_results["stage_2"]["all_active_compound_ids"] as usual,
    but those compound IDs belong to manually-provided structures rather than
    plant-sourced ones. Because manual compounds are not in the compounds table,
    stage 3 uses the inline target-lookup path (ChEMBL/PubChem by InChIKey).

    After injection the endpoint:
    1. Deduplicates submitted compounds by PubChem CID — within batch and against
       any compounds already in stage_1 results.
    2. Stores stage_1 and stage_2 synthetic results in stage_results.
    3. Sets _input_mode = "manual_compounds" in parameters.

    Returns a summary with injected/duplicates_removed/duplicate_names.
    The frontend is responsible for then starting the pipeline.
    """
    import httpx
    from integrations.pubchem_compound import validate_compounds_batch
    from app.services.compound_dedup import deduplicate_compounds

    run = await analysis_repo.get_run(session, analysis_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if run.status not in ("pending", "failed"):
        raise HTTPException(status_code=409, detail="Analysis already running or complete")

    # Collect compound IDs already present in this analysis (stage_1 results)
    existing_stage1 = (run.stage_results or {}).get("stage_1") or {}
    existing_ids: set[str] = set(existing_stage1.get("compound_ids", []))

    # Single shared client for both dedup PubChem lookups and batch validation.
    async with httpx.AsyncClient(timeout=20.0) as client:
        # Deduplicate submitted inputs against each other and existing stage_1 compounds
        try:
            deduped_inputs, dedup_removed = await deduplicate_compounds(
                submitted=body.compounds,
                existing_ids=existing_ids,
                client=client,
            )
        except Exception as e:
            logger.warning("Deduplication failed, proceeding with raw inputs: %s", e, exc_info=True)
            deduped_inputs = body.compounds
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
            raise HTTPException(status_code=503, detail=PUBCHEM_UNAVAILABLE)
        except Exception as e:
            logger.error("PubChem batch validation error: %s", e, exc_info=True)
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
    from app.services.compound_persist import persist_validated_compounds
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


@router.post("/{analysis_id}/user-compounds", response_model=AddUserCompoundResponse, status_code=200)
async def add_user_compound(
    analysis_id: UUID,
    body: AddUserCompoundRequest,
    session: AsyncSession = Depends(get_session),
):
    """Add a single compound to Stage 1 results (post-fetch curation). Validates via PubChem."""
    import httpx
    from integrations.pubchem_compound import validate_compound

    run = await analysis_repo.get_run(session, analysis_id)
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
    run = await analysis_repo.get_run(session, analysis_id)
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
    run = await analysis_repo.get_run(session, analysis_id)
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
    run = await analysis_repo.get_run(session, analysis_id)
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
    run = await analysis_repo.get_run(session, analysis_id)
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


@router.post("/{analysis_id}/inject-targets", response_model=InjectTargetsResponse, status_code=200)
async def inject_targets(
    analysis_id: UUID,
    body: InjectTargetsRequest,
    session: AsyncSession = Depends(get_session),
):
    """Validate gene symbols or UniProt accessions via UniProt and inject as stage 3 results.

    Enables manual target input mode (T4.4): stages 1–3 are skipped and stage 4
    is the first real stage. The synthetic stage_3 result stores the validated targets
    in the format stage 5 reads (target_gene_symbols) and stage 4 ignores stage 3 entirely.

    After injection the endpoint:
    1. Deduplicates submitted targets by UniProt accession — within batch and
       against targets already in stage_3 results.
    2. Stores a synthetic stage_3 result in stage_results.
    3. Sets _input_mode = "manual_targets" in parameters.

    Returns a summary with injected/failed/duplicates_removed/duplicate_names.
    The frontend is responsible for then starting the pipeline.
    """
    import re
    import asyncio
    from app.services.target_dedup import deduplicate_targets

    UNIPROT_ACCESSION_RE = re.compile(
        r"^[OPQ][0-9][A-Z0-9]{3}[0-9](?:[A-Z][A-Z0-9]{2}[0-9])?$"
        r"|^[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}$",
        re.IGNORECASE,
    )

    import re as _re
    _INJECT_TARGETS_ALLOWED = _re.compile(r"^(pending|failed|stage_[1-4]_awaiting_approval)$")

    run = await analysis_repo.get_run(session, analysis_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not _INJECT_TARGETS_ALLOWED.match(run.status or ""):
        raise HTTPException(status_code=409, detail="Analysis already running or complete")

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
    for raw in body.targets:
        raw_stripped = raw.strip()
        if not raw_stripped:
            submitted_dicts.append({"_raw": raw})
            continue
        is_accession = bool(UNIPROT_ACCESSION_RE.match(raw_stripped))
        if is_accession:
            submitted_dicts.append({"uniprot_id": raw_stripped, "_raw": raw})
        else:
            submitted_dicts.append({"gene_symbol": raw_stripped, "_raw": raw})

    # skip_validation bypasses UniProt entirely — no dedup needed either
    if body.skip_validation:
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
    if body.skip_validation:
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
        is_accession = bool(UNIPROT_ACCESSION_RE.match(raw_stripped))
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


@router.delete("/{analysis_id}/disease-targets/{gene_symbol}", status_code=204)
async def remove_user_disease_target(
    analysis_id: UUID,
    gene_symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Remove any target from Stage 4 results by gene symbol."""
    run = await analysis_repo.get_run(session, analysis_id)
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
