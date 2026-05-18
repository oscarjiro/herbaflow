import csv
import io
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session, async_session_factory
from app.schemas.analysis import CreateAnalysisRequest, AnalysisStatusResponse, AnalysisRunResponse
from app.repositories import analysis_repo
from analysis.pipeline import run_stage

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
    parameters = {
        **body.parameters,
        "_plant_ids": [str(pid) for pid in body.plant_ids],
        "_disease_ids": [str(did) for did in body.disease_ids],
    }
    run = await analysis_repo.create_run(session, body.name, body.mode, parameters)
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

    # CSV: flatten for tabular stages (stage 7 hub genes is the most useful)
    if stage_key == "stage_7":
        rows = stage_data.get("ranked", [])
        if rows:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={run.analysis_name}_hub_genes.csv"},
            )

    # Default: return JSON even when csv requested
    content = json.dumps(stage_data, indent=2)
    return StreamingResponse(
        io.StringIO(content),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={run.analysis_name}_{stage_key}.json"},
    )
