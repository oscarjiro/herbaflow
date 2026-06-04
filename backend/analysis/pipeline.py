import asyncio
import logging
from uuid import UUID
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.repositories import analysis_repo
from app.security import client_error_message
from integrations._retry import ServiceUnavailableError
from analysis.models import PipelineConfig
from analysis import stage_state
from analysis.stages import (
    stage1_selection,
    stage2_adme,
    stage3_targets,
    stage4_disease_targets,
    stage5_overlap,
    stage6_ppi,
    stage7_hub_genes,
    stage8_enrichment,
)

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = get_settings().heartbeat_interval_seconds


async def _heartbeat_loop(
    analysis_id: UUID,
    session_factory: sessionmaker,
) -> None:
    """Periodically bump the run's updated_at while a stage executes so a reaper can
    distinguish a live-but-slow run from a dead one. Reads the module-global interval
    each iteration so tests can monkeypatch it. Best-effort: a failed write is logged,
    never raised, so the ticker keeps running."""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        try:
            async with session_factory() as session:
                await analysis_repo.touch_heartbeat(session, analysis_id)
        except Exception:
            logger.warning("Heartbeat write failed for analysis %s", analysis_id)

STAGE_RUNNERS = {
    1: stage1_selection.run,
    2: stage2_adme.run,
    3: stage3_targets.run,
    4: stage4_disease_targets.run,
    5: stage5_overlap.run,
    6: stage6_ppi.run,
    7: stage7_hub_genes.run,
    8: stage8_enrichment.run,
}


async def _record_failure(session_factory, analysis_id, kind: str, message: str) -> None:
    """Record a run as failed with a failure-kind marker. Best-effort: if the DB
    write itself fails (e.g. DB outage), log and return — never let the exception
    escape the background task (the reaper cleans the frozen run)."""
    try:
        async with session_factory() as session:
            await analysis_repo.update_run_status(
                session, analysis_id,
                status="failed",
                error_message=message,
                stage_results={"_run_health": {"failure_kind": kind}},
            )
    except Exception:
        logger.exception(
            "Could not record failure for analysis %s (DB unavailable?)", analysis_id
        )


async def run_stage(
    analysis_id: UUID,
    stage_num: int,
    session_factory: sessionmaker,
) -> None:
    async with session_factory() as session:
        run = await analysis_repo.get_run(session, analysis_id)
        if run is None or run.status == "failed":
            return

        config = PipelineConfig.from_dict(run.parameters)
        stage_fn = STAGE_RUNNERS.get(stage_num)
        if stage_fn is None:
            return

        await analysis_repo.update_run_status(
            session, analysis_id,
            status=f"stage_{stage_num}_running",
            current_stage=stage_num,
        )

    try:
        hb = asyncio.create_task(_heartbeat_loop(analysis_id, session_factory))
        try:
            async with session_factory() as session:
                run = await analysis_repo.get_run(session, analysis_id)
                stage_result = await stage_fn(run, config, session)
                stage_result.setdefault("state", stage_state.COMPUTED)
        finally:
            hb.cancel()

        async with session_factory() as session:
            run = await analysis_repo.get_run(session, analysis_id)
            is_last = stage_num == 8
            if is_last:
                await analysis_repo.update_run_status(
                    session, analysis_id,
                    status="complete",
                    stage_results={f"stage_{stage_num}": stage_result},
                    completed=True,
                )
            elif run.mode == "guided":
                await analysis_repo.update_run_status(
                    session, analysis_id,
                    status=f"stage_{stage_num}_awaiting_approval",
                    stage_results={f"stage_{stage_num}": stage_result},
                )
            else:
                await analysis_repo.update_run_status(
                    session, analysis_id,
                    status=f"stage_{stage_num}_complete",
                    stage_results={f"stage_{stage_num}": stage_result},
                )
                asyncio.create_task(
                    run_stage(analysis_id, stage_num + 1, session_factory)
                )

    except ServiceUnavailableError as exc:
        logger.warning(
            "Stage %s provider unavailable for analysis %s: %s",
            stage_num, analysis_id, exc,
        )
        await _record_failure(
            session_factory, analysis_id,
            kind="provider_unavailable", message=str(exc),
        )
    except Exception:
        logger.exception(
            "Stage %s failed for analysis %s", stage_num, analysis_id
        )
        await _record_failure(
            session_factory, analysis_id,
            kind="internal_error", message=client_error_message(stage_num),
        )


async def advance_pipeline(
    analysis_id: UUID,
    session_factory: sessionmaker,
) -> None:
    """Called by POST /analyses/{id}/approve to start the next stage."""
    async with session_factory() as session:
        run = await analysis_repo.get_run(session, analysis_id)
        if run is None:
            return
        status = run.status
        if not status.endswith("_awaiting_approval"):
            return
        try:
            stage_num = int(status.split("_")[1])
        except (IndexError, ValueError):
            return
        next_stage = stage_num + 1
        if next_stage > 8:
            return

    await run_stage(analysis_id, next_stage, session_factory)


_FIRST_REAL_STAGE = {
    "standard": 1,
    "manual_compounds": 2,
    "manual_targets": 4,
}


async def start_pipeline(
    analysis_id: UUID,
    plant_ids: list[str],
    disease_id: str | None,
    session_factory: sessionmaker,
) -> None:
    async with session_factory() as session:
        run = await analysis_repo.get_run(session, analysis_id)
        params = run.parameters or {}
        params["_plant_ids"] = plant_ids
        params["_disease_id"] = disease_id
        run.parameters = params
        session.add(run)
        await session.commit()

    # Determine which stages (if any) to skip based on _input_mode.
    async with session_factory() as session:
        run = await analysis_repo.get_run(session, analysis_id)
        input_mode = (run.parameters or {}).get("_input_mode", "standard")

    first_real = _FIRST_REAL_STAGE.get(input_mode, 1)

    if first_real > 1:
        async with session_factory() as session:
            run = await analysis_repo.get_run(session, analysis_id)
            existing = run.stage_results or {}
            # Mark only the genuinely-empty pre-entry stages as not_applicable.
            # Stages the inject step already populated (user_provided entries) are
            # left untouched — overwriting them would discard the user's input.
            na_states = {
                f"stage_{n}": {"state": stage_state.NOT_APPLICABLE}
                for n in range(1, first_real)
                if f"stage_{n}" not in existing
            }
        async with session_factory() as session:
            await analysis_repo.update_run_status(
                session,
                analysis_id,
                status=f"stage_{first_real}_running",
                current_stage=first_real,
                stage_results=na_states,  # may be empty (manual_compounds): harmless merge
            )

    await run_stage(analysis_id, first_real, session_factory)
