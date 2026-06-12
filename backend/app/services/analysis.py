"""Analysis run service: validate, create, fetch, advance."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import contracts
from app.clock import now_utc
from app.errors import ConflictProblem, GoneProblem, NotFoundProblem, ValidationProblem
from app.pipeline import edits, engine, entry_modes, state
from app.pipeline.limits import EntityCapExceeded, check_entity_cap
from app.repositories.analysis import AnalysisRepository
from app.repositories.compound import CompoundRepository
from app.repositories.compound_target import CompoundTargetRepository
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
        compound_target_repo: Any = None,
    ) -> None:
        self.plant_repo = plant_repo
        self.disease_repo = disease_repo
        self.analysis_repo = analysis_repo
        self.compound_repo = compound_repo
        self.target_repo = target_repo
        self.compound_target_repo = compound_target_repo

    @classmethod
    def from_session(cls, session: AsyncSession) -> AnalysisService:
        return cls(
            plant_repo=PlantRepository(session),
            disease_repo=DiseaseRepository(session),
            analysis_repo=AnalysisRepository(session),
            compound_repo=CompoundRepository(session),
            target_repo=TargetRepository(session),
            compound_target_repo=CompoundTargetRepository(session),
        )

    async def create(self, payload: AnalysisCreate) -> AnalysisRead:
        plant_mode = payload.plant_input_mode.value
        disease_mode = payload.disease_input_mode.value
        logger.info(
            "creating analysis: plant_mode=%s, disease_mode=%s, %d plant(s), disease %s, mode=%s",
            plant_mode,
            disease_mode,
            len(payload.plant_ids),
            str(payload.disease_id)[:8],
            payload.mode.value,
        )

        # Referential existence — only the lists relevant to the chosen modes (the schema already
        # enforced which lists are present/forbidden per mode). Selection plants are validated by
        # the plant repo; manual compounds (whether the S1 entities in manual_compounds mode OR
        # the Chunk-1 manual additions unioned into a selection-mode Stage 1) and manual targets
        # are validated for cap + existence.
        if plant_mode == "selection":
            missing = await self.plant_repo.missing_ids(payload.plant_ids)
            if missing:
                raise ValidationProblem(
                    detail="Unknown plant ids.", invalid_plant_ids=[str(p) for p in missing]
                )
        if payload.manual_compound_ids:
            await self._verify_entities("compound", self.compound_repo, payload.manual_compound_ids)
        if plant_mode == "manual_targets":
            await self._verify_entities("target", self.target_repo, payload.manual_target_ids)

        if disease_mode == "selection":
            if not await self.disease_repo.exists(payload.disease_id):
                raise ValidationProblem(
                    detail="Unknown disease id.", invalid_disease_id=str(payload.disease_id)
                )
        else:  # manual_disease_targets
            await self._verify_entities(
                "target", self.target_repo, payload.manual_disease_target_ids
            )

        # Stage-state matrix + run cursor (first computed stage), derived from the chosen modes.
        smap = entry_modes.stage_state_map(plant_mode, disease_mode)
        current_stage = entry_modes.first_computed_stage(plant_mode, disease_mode)

        stage_edits: dict[str, Any] = {}
        stage_results: dict[str, Any] = {}

        # Stamp not_applicable stages (no entities flow through them at all).
        for stage, st in smap.items():
            if st == entry_modes.NOT_APPLICABLE:
                stage_results[str(stage)] = {"state": entry_modes.NOT_APPLICABLE, "count": 0}

        # Pre-fill user-provided ENTITY stages THROUGH the durable edit layer so they survive
        # edits + reset-from. S1 = manual compounds; S3 = manual targets; S4 = manual disease
        # targets (which also writes the disease_targets view list S5 reads).
        if smap[1] == entry_modes.USER_PROVIDED:
            self._prefill_compound_stage(1, payload.manual_compound_ids, stage_edits, stage_results)
        if smap[3] == entry_modes.USER_PROVIDED:
            await self._prefill_target_stage(
                3, payload.manual_target_ids, stage_edits, stage_results
            )
        if smap[4] == entry_modes.USER_PROVIDED:
            await self._prefill_disease_target_stage(
                payload.manual_disease_target_ids, stage_edits, stage_results
            )

        # Atomicity guard: a user-provided stage that resolved to zero usable entities is an
        # empty pipeline — reject the whole create (422), nothing is persisted.
        for stage, st in smap.items():
            if st == entry_modes.USER_PROVIDED and stage_results[str(stage)].get("count", 0) == 0:
                raise ValidationProblem(
                    detail=(
                        f"No usable entities resolved for the user-provided stage {stage}; "
                        "the run would be empty."
                    )
                )

        pipeline_parameters = {
            "adme": contracts.adme_defaults(),
            "target": contracts.target_defaults(),
            "disease_targets": contracts.disease_targets_defaults(),
            "ppi": contracts.ppi_defaults(),
            "hub_genes": contracts.hub_genes_defaults(),
            "enrichment": contracts.enrichment_defaults(),
        }
        extra_parameters: dict[str, Any] = {
            "input_modes": {"plant": plant_mode, "disease": disease_mode}
        }
        labels: dict[str, str] = {}
        if payload.plant_label is not None:
            labels["plant"] = payload.plant_label
        if payload.disease_label is not None:
            labels["disease"] = payload.disease_label
        if labels:
            extra_parameters["labels"] = labels

        run = await self.analysis_repo.create(
            analysis_name=payload.analysis_name,
            disease_id=payload.disease_id,
            plant_ids=payload.plant_ids,
            mode=payload.mode.value,
            manual_compound_ids=payload.manual_compound_ids,
            pipeline_parameters=pipeline_parameters,
            extra_parameters=extra_parameters,
            stage_edits=stage_edits,
            stage_results=stage_results,
            current_stage=current_stage,
        )
        return AnalysisRead.model_validate(run)

    async def _verify_entities(self, entity: str, repo: Any, ids: list[uuid.UUID]) -> None:
        """Enforce the entity cap then existence for a manual-input id list (422 on failure)."""
        try:
            check_entity_cap(entity, current=0, adding=len(ids))
        except EntityCapExceeded as e:
            raise ValidationProblem(
                detail=f"Too many manual {entity}s (max {e.cap}, got {e.adding})."
            ) from e
        existing = await repo.existing_ids(ids)
        missing = [i for i in ids if i not in existing]
        if missing:
            raise ValidationProblem(
                detail=f"Unknown {entity} ids.",
                **{f"invalid_{entity}_ids": [str(i) for i in missing]},
            )

    def _prefill_compound_stage(
        self,
        stage: int,
        ids: list[uuid.UUID],
        stage_edits: dict[str, Any],
        stage_results: dict[str, Any],
    ) -> None:
        """Seed a user-provided compound stage (S1) through the durable edit layer."""
        edit = edits.normalize_edit(
            edits.empty_edit(),
            [{"compound_id": str(i), "canonical_name": None} for i in ids],
            [],
            id_key="compound_id",
        )
        stage_edits[str(stage)] = edit
        stage_results[str(stage)] = edits.build_stage_entities(
            [], edit, id_key="compound_id", list_key="compounds"
        )

    async def _prefill_target_stage(
        self,
        stage: int,
        ids: list[uuid.UUID],
        stage_edits: dict[str, Any],
        stage_results: dict[str, Any],
    ) -> None:
        """Seed a user-provided target stage (S3) through the edit layer + the Stage-3 view extras.

        Target rows carry gene_symbol / uniprot_accession so the edit layer keeps them (the linchpin
        the downstream STRING / g:Profiler stages depend on).
        """
        rows = await self.target_repo.get_many(ids)
        edit = edits.normalize_edit(
            edits.empty_edit(), [self._target_add_entry(t) for t in rows], [], id_key="target_id"
        )
        stage_edits[str(stage)] = edit
        stage_results[str(stage)] = {
            **edits.build_stage_entities([], edit, id_key="target_id", list_key="targets"),
            "compound_targets": [],
            "per_compound": {},
            "coverage_pct": 0.0,
        }

    async def _prefill_disease_target_stage(
        self,
        ids: list[uuid.UUID],
        stage_edits: dict[str, Any],
        stage_results: dict[str, Any],
    ) -> None:
        """Seed user-provided Stage 4 through BOTH the edit layer AND the ``disease_targets`` view.

        Stage 5 reads ``stage4["disease_targets"]`` (a separate view list), NOT the edit-layer
        ``targets`` — so both are written, each carrying the target's real gene_symbol /
        uniprot_accession. The disease→target relationship is run-scoped only (no canonical edge,
        no association score; Software Lock §6.2-E).
        """
        rows = await self.target_repo.get_many(ids)
        edit = edits.normalize_edit(
            edits.empty_edit(), [self._target_add_entry(t) for t in rows], [], id_key="target_id"
        )
        stage_edits["4"] = edit
        frag = edits.build_stage_entities([], edit, id_key="target_id", list_key="targets")
        disease_targets = [
            {
                "target_id": str(t.target_id),
                "gene_symbol": t.gene_symbol,
                "uniprot_accession": t.uniprot_accession,
                "score": None,
                "association_type": None,
                "source_url": (
                    f"https://www.uniprot.org/uniprotkb/{t.uniprot_accession}/entry"
                    if t.uniprot_accession
                    else None
                ),
            }
            for t in rows
        ]
        stage_results["4"] = {**frag, "disease_targets": disease_targets, "min_score_applied": None}

    @staticmethod
    def _target_add_entry(t: Any) -> dict[str, Any]:
        """Edit-layer add entry for a target, carrying its identity fields.

        The display name uses the real ``Target`` attributes (there is no ``canonical_name``
        column): gene_symbol, then protein_name, then the accession.
        """
        return {
            "target_id": str(t.target_id),
            "canonical_name": t.gene_symbol or t.protein_name or t.uniprot_accession,
            "gene_symbol": t.gene_symbol,
            "uniprot_accession": t.uniprot_accession,
        }

    async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
        run = await self.analysis_repo.get(analysis_id)
        if run is None:
            raise NotFoundProblem(detail="Analysis run not found.")
        if run.expires_at is not None and run.expires_at < now_utc():
            raise GoneProblem(detail="Analysis run has expired.")
        return AnalysisRead.model_validate(run)

    async def advance(self, analysis_id: uuid.UUID, *, defer: bool = False) -> int | None:
        runners = engine.build_runners(self.analysis_repo.session)
        return await engine.advance_run(self.analysis_repo, analysis_id, runners, defer=defer)

    async def reset_from(
        self,
        analysis_id: uuid.UUID,
        stage: int,
        param_overrides: dict[str, Any] | None,
        *,
        defer: bool = False,
    ) -> frozenset[int] | None:
        """Re-run a settled run from ``stage`` (param Redo or set edit) via the engine.

        Returns the run-set to schedule (``defer=True``) or ``None`` (no-op / no runnable
        dependent / executed inline).
        """
        runners = engine.build_runners(self.analysis_repo.session)
        return await engine.reset_from(
            self.analysis_repo,
            analysis_id,
            stage,
            runners,
            param_overrides=param_overrides,
            defer=defer,
        )

    async def edit_stage(
        self,
        analysis_id: uuid.UUID,
        stage: int,
        *,
        add: list[uuid.UUID],
        remove: list[uuid.UUID],
    ) -> None:
        """Apply a durable in-stage entity edit (add/remove) and stage the change.

        Validates added ids exist, enforces the entity cap on net additions, folds the edit into
        the durable edit layer, and re-derives the edited stage's stored result. An edit may never
        empty a stage: removing the last remaining entity is rejected (422) and nothing is
        persisted. Otherwise it persists the edit, flags produced downstream stages stale, and
        records ``parameters.rerun_from``; nothing is re-run (D3). Recompute happens only on an
        explicit reset-from.
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
        # gene_symbol when no canonical_name attribute is present. Target rows also carry
        # gene_symbol and uniprot_accession so the durable edit layer keeps them for
        # downstream stages (Stage 8 custom background, Stage 3 view).
        add_entries: list[dict[str, Any]] = []
        if add:
            for obj in await repo.get_many(add):
                entry: dict[str, Any] = {
                    id_key: str(getattr(obj, id_key)),
                    "canonical_name": getattr(obj, "canonical_name", None)
                    or getattr(obj, "gene_symbol", None),
                }
                if getattr(obj, "gene_symbol", None) is not None:
                    entry["gene_symbol"] = obj.gene_symbol
                if getattr(obj, "uniprot_accession", None) is not None:
                    entry["uniprot_accession"] = obj.uniprot_accession
                add_entries.append(entry)

        # Fold into the durable edit layer (computed; not yet persisted).
        prior_edit = run.parameters.get("stage_edits", {}).get(skey, edits.empty_edit())
        new_edit = edits.normalize_edit(
            prior_edit, add_entries, [str(r) for r in remove], id_key=id_key
        )

        # Re-derive the edited stage's stored result from its RAW computed entities + new edit.
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

        # Guard: an edit may never empty an entity stage. Reject the removal of the last
        # remaining entity (a stage must keep >= 1). Nothing is persisted on rejection.
        if frag["count"] == 0:
            raise ValidationProblem(
                detail=(
                    f"Cannot remove the last remaining {entity}; a stage must keep at "
                    f"least one {entity}. Add another before removing this one."
                )
            )

        # Persist the new edit + re-derived stored result.
        new_params = dict(run.parameters)
        stage_edits = dict(new_params.get("stage_edits", {}))
        stage_edits[skey] = new_edit
        new_params["stage_edits"] = stage_edits
        run.parameters = new_params
        await self.analysis_repo.set_parameters(run)

        preserved = {k: v for k, v in existing_result.items() if k not in frag and k != list_key}
        await self.analysis_repo.set_stage_result(run, stage, {**preserved, **frag})

        # Stage the edit only (D3): the edited stage was re-derived in place above; the
        # produced downstream is flagged stale and NOT re-run. Recompute happens only on an
        # explicit reset-from. Record the lowest pending edit as the reset-from target.
        await engine.mark_downstream_stale(self.analysis_repo, run, stage)
        produced = {int(k) for k in run.stage_results}
        if engine.downstream_closure(stage) & produced:
            params = dict(run.parameters)
            prior = params.get("rerun_from")
            params["rerun_from"] = stage if prior is None else min(prior, stage)
            run.parameters = params
            await self.analysis_repo.set_parameters(run)
        return None
