"""Analysis run service: validate, create, fetch, advance."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import contracts
from app.clock import now_utc
from app.errors import ConflictProblem, GoneProblem, NotFoundProblem, ValidationProblem
from app.pipeline import edits, engine, state
from app.pipeline.limits import EntityCapExceeded, check_entity_cap
from app.repositories.analysis import AnalysisRepository
from app.repositories.compound import CompoundRepository
from app.repositories.disease import DiseaseRepository
from app.repositories.plant import PlantRepository
from app.repositories.target import TargetRepository
from app.schemas.analysis import AnalysisCreate, AnalysisRead

logger = logging.getLogger("herbaflow.analysis")

# Per editable entity stage: (cap entity, id_key, stored list key). Stage 1 edits compounds;
# Stage 3/4 edit targets. The durable edit layer is threaded with these keys.
_STAGE_ENTITY: dict[int, tuple[str, str, str]] = {
    1: ("compound", "compound_id", "compounds"),
    3: ("target", "target_id", "targets"),
    4: ("target", "target_id", "targets"),
}


class AnalysisService:
    def __init__(
        self,
        *,
        plant_repo: Any,
        disease_repo: Any,
        analysis_repo: Any,
        compound_repo: Any,
        target_repo: Any = None,
    ) -> None:
        self.plant_repo = plant_repo
        self.disease_repo = disease_repo
        self.analysis_repo = analysis_repo
        self.compound_repo = compound_repo
        self.target_repo = target_repo

    @classmethod
    def from_session(cls, session: AsyncSession) -> AnalysisService:
        return cls(
            plant_repo=PlantRepository(session),
            disease_repo=DiseaseRepository(session),
            analysis_repo=AnalysisRepository(session),
            compound_repo=CompoundRepository(session),
            target_repo=TargetRepository(session),
        )

    async def create(self, payload: AnalysisCreate) -> AnalysisRead:
        logger.info(
            "creating analysis: %d plant(s), disease %s, %d manual compound(s), mode=%s",
            len(payload.plant_ids),
            str(payload.disease_id)[:8],
            len(payload.manual_compound_ids),
            payload.mode.value,
        )
        missing = await self.plant_repo.missing_ids(payload.plant_ids)
        if missing:
            raise ValidationProblem(
                detail="Unknown plant ids.", invalid_plant_ids=[str(p) for p in missing]
            )
        if not await self.disease_repo.exists(payload.disease_id):
            raise ValidationProblem(
                detail="Unknown disease id.", invalid_disease_id=str(payload.disease_id)
            )
        if payload.manual_compound_ids:
            try:
                check_entity_cap("compound", current=0, adding=len(payload.manual_compound_ids))
            except EntityCapExceeded as e:
                raise ValidationProblem(
                    detail=f"Too many manual compounds (max {e.cap}, got {e.adding})."
                ) from e
            existing = await self.compound_repo.existing_ids(payload.manual_compound_ids)
            missing = [c for c in payload.manual_compound_ids if c not in existing]
            if missing:
                raise ValidationProblem(
                    detail="Unknown compound ids.",
                    invalid_compound_ids=[str(c) for c in missing],
                )
        pipeline_parameters = {
            "adme": contracts.adme_defaults(),
            "target": contracts.target_defaults(),
        }
        run = await self.analysis_repo.create(
            analysis_name=payload.analysis_name,
            disease_id=payload.disease_id,
            plant_ids=payload.plant_ids,
            mode=payload.mode.value,
            manual_compound_ids=payload.manual_compound_ids,
            pipeline_parameters=pipeline_parameters,
        )
        return AnalysisRead.model_validate(run)

    async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
        run = await self.analysis_repo.get(analysis_id)
        if run is None:
            raise NotFoundProblem(detail="Analysis run not found.")
        if run.expires_at is not None and run.expires_at < now_utc():
            raise GoneProblem(detail="Analysis run has expired.")
        return AnalysisRead.model_validate(run)

    async def advance(self, analysis_id: uuid.UUID) -> None:
        runners = engine.build_runners(self.analysis_repo.session)
        await engine.advance_run(self.analysis_repo, analysis_id, runners)

    async def reset_from(
        self,
        analysis_id: uuid.UUID,
        stage: int,
        param_overrides: dict[str, Any] | None,
    ) -> None:
        """Re-run a settled run from ``stage`` (param Redo or set edit) via the engine."""
        runners = engine.build_runners(self.analysis_repo.session)
        await engine.reset_from(
            self.analysis_repo, analysis_id, stage, runners, param_overrides=param_overrides
        )

    async def edit_stage(
        self,
        analysis_id: uuid.UUID,
        stage: int,
        *,
        add: list[uuid.UUID],
        remove: list[uuid.UUID],
    ) -> None:
        """Apply a durable in-stage entity edit (add/remove) and re-run downstream.

        Validates added ids exist, enforces the entity cap on net additions, folds the edit into
        the durable edit layer, re-derives the edited stage's stored result, and either fails the
        run (empty effective set, E3) or triggers a dependency-aware set-edit re-run.
        """
        entity_keys = _STAGE_ENTITY.get(stage)
        if entity_keys is None:
            raise ValidationProblem(detail=f"Stage {stage} is not an editable entity stage.")
        entity, id_key, list_key = entity_keys
        repo = self.target_repo if entity == "target" else self.compound_repo

        run = await self.analysis_repo.get(analysis_id)
        if run is None:
            raise NotFoundProblem(detail="Analysis run not found.")

        # Settled guard (engine.reset_from re-checks; guard here so the edit never half-applies).
        if not state.is_settled(run.status):
            raise ConflictProblem(
                detail="Run is still running; wait for it to settle before editing."
            )

        skey = str(stage)
        existing_result = run.stage_results.get(skey)
        if existing_result is None:
            raise ValidationProblem(detail=f"Stage {stage} has not been computed yet.")

        # Verify added ids exist.
        if add:
            existing_ids = await repo.existing_ids(add)
            missing = [c for c in add if c not in existing_ids]
            if missing:
                raise ValidationProblem(
                    detail=f"Unknown {entity} ids.",
                    **{f"invalid_{entity}_ids": [str(x) for x in missing]},
                )

        # Cap on net additions: current effective size + |add| <= cap.
        current_effective = sum(
            1 for c in existing_result[list_key] if c.get("tag") != "user-removed"
        )
        if add:
            try:
                check_entity_cap(entity, current=current_effective, adding=len(add))
            except EntityCapExceeded as e:
                raise ValidationProblem(
                    detail=(
                        f"Too many {entity}s for this stage (max {e.cap}, "
                        f"have {e.current}, adding {e.adding})."
                    )
                ) from e

        # Resolve added entities' names (self-contained edit layer); targets fall back to
        # gene_symbol when no canonical_name attribute is present.
        add_entries: list[dict[str, Any]] = []
        if add:
            for obj in await repo.get_many(add):
                add_entries.append(
                    {
                        id_key: str(getattr(obj, id_key)),
                        "canonical_name": getattr(obj, "canonical_name", None)
                        or getattr(obj, "gene_symbol", None),
                    }
                )

        # Fold into the durable edit layer.
        prior_edit = run.parameters.get("stage_edits", {}).get(skey, edits.empty_edit())
        new_edit = edits.normalize_edit(
            prior_edit, add_entries, [str(r) for r in remove], id_key=id_key
        )
        new_params = dict(run.parameters)
        stage_edits = dict(new_params.get("stage_edits", {}))
        stage_edits[skey] = new_edit
        new_params["stage_edits"] = stage_edits
        run.parameters = new_params
        await self.analysis_repo.set_parameters(run)

        # Re-derive the edited stage's stored result from its RAW computed entities + the new edit.
        computed_ids = existing_result["computed_ids"]
        names = {c[id_key]: c.get("canonical_name") for c in existing_result[list_key]}
        for entry in new_edit["added"]:
            names.setdefault(entry[id_key], entry.get("canonical_name"))
        computed_entities = [
            {id_key: cid, "canonical_name": names.get(cid)} for cid in computed_ids
        ]
        frag = edits.build_stage_entities(
            computed_entities, new_edit, id_key=id_key, list_key=list_key
        )
        preserved = {k: v for k, v in existing_result.items() if k not in frag and k != list_key}
        await self.analysis_repo.set_stage_result(run, stage, {**preserved, **frag})

        # E3: empty effective set -> fail, no re-run.
        if frag["count"] == 0:
            await self.analysis_repo.fail(
                run, f"No {entity}s remain after editing; add at least one {entity}."
            )
            return

        # Set-edit re-run: clears downstream, re-runs from the nearest runnable dependent.
        runners = engine.build_runners(self.analysis_repo.session)
        await engine.reset_from(self.analysis_repo, analysis_id, stage, runners)
