import copy
import csv
import io
import json
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session, async_session_factory
from app.schemas.analysis import CreateAnalysisRequest, AnalysisStatusResponse, AnalysisRunResponse
from app.schemas.import_targets import ImportTargetsRequest, ImportTargetsResponse, STPTarget
from app.models.target import Target, CompoundTarget
from app.repositories import analysis_repo
from analysis.pipeline import run_stage
from analysis.stages.stage3_targets import _make_target_id, _make_ct_id

router = APIRouter(prefix="/analyses", tags=["analyses"])

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
    from analysis.pipeline import start_pipeline  # imported here; pipeline.py created in Task 11
    if not body.disease_ids:
        raise HTTPException(
            status_code=422,
            detail="disease_ids must contain at least one disease ID",
        )
    parameters = {
        **body.parameters,
        "_plant_ids": [str(pid) for pid in body.plant_ids],
        "_disease_ids": [str(did) for did in body.disease_ids],
    }
    run = await analysis_repo.create_run(
        session, body.name, body.mode, parameters, disease_id=body.disease_ids[0]
    )
    background_tasks.add_task(
        start_pipeline, run.analysis_id, body.plant_ids, body.disease_ids, async_session_factory
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
    )


@router.get("/{analysis_id}", response_model=AnalysisRunResponse)
async def get_analysis(analysis_id: UUID, session: AsyncSession = Depends(get_session)):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisRunResponse(**run.model_dump())


@router.post("/{analysis_id}/approve")
async def approve_stage(
    analysis_id: UUID,
    background_tasks: BackgroundTasks,
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
            # One row per group showing compound IDs and their ADME status
            fieldnames = ["status", "compound_id"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for cid in stage_data.get("passed_compound_ids", []):
                writer.writerow({"status": "passed", "compound_id": cid})
            for cid in stage_data.get("np_exception_compound_ids", []):
                writer.writerow({"status": "np_exception", "compound_id": cid})
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
                fieldnames = ["gene_symbol", "uniprot_accession", "score", "disease_name", "source"]
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for t in targets:
                    writer.writerow({
                        "gene_symbol": t.get("gene_symbol", ""),
                        "uniprot_accession": t.get("uniprot_accession", ""),
                        "score": t.get("score", ""),
                        "disease_name": t.get("disease_name", ""),
                        "source": t.get("source", ""),
                    })
            else:
                writer = csv.DictWriter(output, fieldnames=["gene_symbol", "uniprot_accession", "score", "disease_name", "source"])
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
            # One row per edge (most useful for network analysis)
            edges = stage_data.get("edges", [])
            fieldnames = ["source", "target", "combined_score", "experimental_score"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for e in edges:
                writer.writerow({
                    "source": e.get("source", ""),
                    "target": e.get("target", ""),
                    "combined_score": e.get("combined_score", ""),
                    "experimental_score": e.get("experimental_score", ""),
                })
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
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
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
            target_id = _make_target_id(stp_t.uniprot_id, stp_t.gene_symbol)

            # Upsert Target row
            existing_target = (await session.exec(
                select(Target).where(Target.target_id == target_id)
            )).one_or_none()
            if existing_target is None:
                session.add(Target(
                    target_id=target_id,
                    canonical_key=f"uniprot:{stp_t.uniprot_id}",
                    gene_symbol=stp_t.gene_symbol.upper(),
                    uniprot_accession=stp_t.uniprot_id,
                    organism_tax_id=9606,
                    retrieved_at=now,
                ))

            # Upsert CompoundTarget row
            ct_id = _make_ct_id(body.compound_id, target_id)
            existing_ct = (await session.exec(
                select(CompoundTarget).where(CompoundTarget.compound_target_id == ct_id)
            )).one_or_none()
            if existing_ct is None:
                session.add(CompoundTarget(
                    compound_target_id=ct_id,
                    compound_id=body.compound_id,
                    target_id=target_id,
                    prediction_method="stp_import",
                    evidence_type="computational",
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
