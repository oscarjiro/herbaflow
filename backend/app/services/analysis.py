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
from app.pipeline.engine import validate_overrides
from app.pipeline.limits import EntityCapExceeded, check_entity_cap
from app.repositories.analysis import AnalysisRepository
from app.repositories.analysis_progress import AnalysisProgressRepository
from app.repositories.compound import CompoundRepository
from app.repositories.compound_target import CompoundTargetRepository
from app.repositories.disease import DiseaseRepository
from app.repositories.plant import PlantRepository
from app.repositories.target import TargetRepository
from app.schemas.analysis import AnalysisCreate, AnalysisListItem, AnalysisRead, ProgressRead

logger = logging.getLogger("herbaflow.analysis")

# Statuses that indicate a live per-item stage is running and may have progress rows.
_PROGRESS_RUNNING = {state.stage_status(2, "running"), state.stage_status(3, "running")}

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
        progress_repo: Any = None,
    ) -> None:
        self.plant_repo = plant_repo
        self.disease_repo = disease_repo
        self.analysis_repo = analysis_repo
        self.compound_repo = compound_repo
        self.target_repo = target_repo
        self.compound_target_repo = compound_target_repo
        self.progress_repo: Any = progress_repo

    @classmethod
    def from_session(cls, session: AsyncSession) -> AnalysisService:
        return cls(
            plant_repo=PlantRepository(session),
            disease_repo=DiseaseRepository(session),
            analysis_repo=AnalysisRepository(session),
            compound_repo=CompoundRepository(session),
            target_repo=TargetRepository(session),
            compound_target_repo=CompoundTargetRepository(session),
            progress_repo=AnalysisProgressRepository(session),
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
        # the plant repo; manual compounds (the S1 entities in manual_compounds mode) and manual
        # targets are validated for cap + existence.
        if plant_mode == "selection":
            missing = await self.plant_repo.missing_ids(payload.plant_ids)
            if missing:
                raise ValidationProblem(
                    detail="Unknown plant ids.", invalid_plant_ids=[str(p) for p in missing]
                )
        if plant_mode == "manual_compounds":
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
        # targets (one enriched edit-layer targets list — S5 reads it directly).
        if smap[1] == entry_modes.USER_PROVIDED:
            await self._prefill_compound_stage(
                1, payload.manual_compound_ids, stage_edits, stage_results
            )
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

        # Apply per-group parameter overrides from the create request (if any).
        # Validation happens before any persistence: a bad override rejects the whole create
        # (422) and nothing is written. Unknown groups and unknown keys within a valid group are
        # both rejected. The merged dict becomes the run's frozen parameter baseline.
        if payload.parameters:
            for group, overrides in payload.parameters.items():
                if group not in pipeline_parameters:
                    raise ValidationProblem(detail=f"Unknown parameter group: {group}.")
                if not isinstance(overrides, dict):
                    raise ValidationProblem(detail=f"Parameters for {group} must be an object.")
                validate_overrides(group, overrides)  # 422 on bad bound/type/enum/unknown key
                pipeline_parameters[group].update(overrides)  # merge over defaults

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

    async def _prefill_compound_stage(
        self,
        stage: int,
        ids: list[uuid.UUID],
        stage_edits: dict[str, Any],
        stage_results: dict[str, Any],
    ) -> None:
        """Seed a user-provided compound stage (S1) through the durable edit layer.

        Carries each compound's canonical_name so Stage 1 shows the name, not the UUID
        (symmetric with selection mode + the Stage-3 target prefill). Existence was
        verified upstream in ``create`` (``_verify_entities``), so every id resolves.
        """
        edit = edits.normalize_edit(
            edits.empty_edit(),
            [self._compound_add_entry(c) for c in await self.compound_repo.get_many(ids)],
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
        """Seed user-provided Stage 4 through the durable edit layer (one ``targets`` list).

        Stage 5 reads the edit-layer ``targets`` list directly (there is no separate
        ``disease_targets`` view list any more — B-DUP-2/L-11), so the edit layer carries each
        target's full identity. A manual disease-target has NO disease edge → no association score
        or type (omitted; consumers use ``.get``), but the shared ``_target_add_entry`` carries the
        UniProt ``source_url`` so the FE table + CSV match a computed row — identical to the Stage-3
        prefill (no per-call source_url duplication; B2-sym). The disease→target relationship is
        run-scoped only (no canonical edge, no score; Software Lock §6.2-E).
        """
        rows = await self.target_repo.get_many(ids)
        add_entries = [self._target_add_entry(t) for t in rows]
        edit = edits.normalize_edit(edits.empty_edit(), add_entries, [], id_key="target_id")
        stage_edits["4"] = edit
        stage_results["4"] = {
            **edits.build_stage_entities([], edit, id_key="target_id", list_key="targets"),
            "min_score_applied": None,
        }

    @staticmethod
    def _compound_add_entry(c: Any) -> dict[str, Any]:
        """Edit-layer add entry for a compound, carrying its Stage-1 identity fields."""
        return {
            "compound_id": str(c.compound_id),
            "canonical_name": c.canonical_name,
            "inchikey": getattr(c, "inchi_key", None),
            "smiles": getattr(c, "smiles", None),
            "pubchem_cid": getattr(c, "pubchem_cid", None),
            "source_url": getattr(c, "source_url", None),
        }

    @staticmethod
    def _target_add_entry(t: Any) -> dict[str, Any]:
        """Edit-layer add entry for a target, carrying its identity fields.

        The display name uses the real ``Target`` attributes (there is no ``canonical_name``
        column): gene_symbol, then protein_name, then the accession. Also carries the UniProt
        ``source_url`` (derived from the accession) so EVERY target row — S3/S4 prefill and the
        edit-add path, plant or disease side — renders the same UniProt link symmetrically. This
        is the single home; callers must NOT add ``source_url`` themselves (B2-sym).
        """
        return {
            "target_id": str(t.target_id),
            "canonical_name": t.gene_symbol or t.protein_name or t.uniprot_accession,
            "gene_symbol": t.gene_symbol,
            "uniprot_accession": t.uniprot_accession,
            "source_url": (
                f"https://www.uniprot.org/uniprotkb/{t.uniprot_accession}/entry"
                if t.uniprot_accession
                else None
            ),
        }

    @staticmethod
    def _apply_stp_run_links(
        stage3: dict[str, Any], *, compound_id: str, target_ids: list[str]
    ) -> None:
        """Attach STP links to the run-scoped Stage-3 result and recompute coverage."""
        per_compound = stage3.get("per_compound")
        if not isinstance(per_compound, dict) or compound_id not in per_compound:
            raise ValidationProblem(
                detail="SwissTargetPrediction compound must be present in Stage 3 coverage."
            )

        target_by_id = {
            str(row.get("target_id")): row
            for row in stage3.get("targets", [])
            if row.get("tag") != "user-removed"
        }
        missing = [tid for tid in target_ids if tid not in target_by_id]
        if missing:
            raise ValidationProblem(
                detail="SwissTargetPrediction target ids must be present in Stage 3 targets.",
                invalid_target_ids=missing,
            )

        edges = [dict(edge) for edge in stage3.get("compound_targets", [])]
        existing_pairs = {
            (str(edge.get("compound_id")), str(edge.get("target_id"))) for edge in edges
        }
        for target_id in dict.fromkeys(target_ids):
            pair = (compound_id, target_id)
            if pair in existing_pairs:
                continue
            target = target_by_id[target_id]
            edges.append(
                {
                    "compound_id": compound_id,
                    "target_id": target_id,
                    "prediction_method": "stp_import",
                    "pchembl_value": None,
                    "score": None,
                    "source_url": target.get("source_url"),
                    "uniprot_accession": target.get("uniprot_accession"),
                }
            )
            existing_pairs.add(pair)

        active_target_ids = set(target_by_id)
        coverage_by_compound: dict[str, set[str]] = {str(cid): set() for cid in per_compound}
        for edge in edges:
            cid = str(edge.get("compound_id"))
            tid = str(edge.get("target_id"))
            if cid in coverage_by_compound and tid in active_target_ids:
                coverage_by_compound[cid].add(tid)

        stage3["compound_targets"] = edges
        updated_per_compound: dict[str, dict[str, Any]] = {}
        for cid, tids in coverage_by_compound.items():
            existing = per_compound.get(cid)
            base = dict(existing) if isinstance(existing, dict) else {}
            base["coverage"] = len(tids)
            updated_per_compound[cid] = base
        stage3["per_compound"] = updated_per_compound
        covered = sum(1 for tids in coverage_by_compound.values() if tids)
        total = len(coverage_by_compound)
        stage3["coverage_pct"] = round(100.0 * covered / total, 1) if total else 0.0

    async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
        run = await self.analysis_repo.get(analysis_id)
        if run is None:
            raise NotFoundProblem(detail="Analysis run not found.")
        if run.expires_at is not None and run.expires_at < now_utc():
            raise GoneProblem(detail="Analysis run has expired.")
        read = AnalysisRead.model_validate(run)
        await self._hydrate_stage1_compound_identity(read)
        if run.status in _PROGRESS_RUNNING and self.progress_repo is not None:
            row = await self.progress_repo.get(analysis_id)
            if row is not None:
                read.progress = ProgressRead.model_validate(row)
        return read

    async def _hydrate_stage1_compound_identity(self, read: AnalysisRead) -> None:
        """Fill legacy Stage-1 compound rows that predate edit-layer identity carry.

        Current manual prefill/edit rows already carry these fields. This read-time
        compatibility path only patches old stored rows with missing identity values
        so the API and frontend display the canonical compound record consistently.
        """
        stage1 = read.stage_results.get("1")
        if not isinstance(stage1, dict):
            return
        rows = stage1.get("compounds")
        if not isinstance(rows, list):
            return

        ids: list[uuid.UUID] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not any(
                row.get(key) in (None, "")
                for key in ("inchikey", "smiles", "pubchem_cid", "source_url")
            ):
                continue
            try:
                ids.append(uuid.UUID(str(row["compound_id"])))
            except (KeyError, TypeError, ValueError):
                continue
        if not ids:
            return

        compounds = await self.compound_repo.get_many(ids)
        by_id = {str(c.compound_id): self._compound_add_entry(c) for c in compounds}

        changed = False
        hydrated_rows: list[Any] = []
        for row in rows:
            if not isinstance(row, dict):
                hydrated_rows.append(row)
                continue
            patch = by_id.get(str(row.get("compound_id")))
            if patch is None:
                hydrated_rows.append(row)
                continue
            next_row = dict(row)
            for key in ("canonical_name", "inchikey", "smiles", "pubchem_cid", "source_url"):
                if next_row.get(key) in (None, "") and patch.get(key) is not None:
                    next_row[key] = patch[key]
                    changed = True
            hydrated_rows.append(next_row)

        if changed:
            read.stage_results = {
                **read.stage_results,
                "1": {**stage1, "compounds": hydrated_rows},
            }

    async def list_recent(self, *, limit: int, offset: int) -> list[AnalysisListItem]:
        runs = await self.analysis_repo.list_recent(limit=limit, offset=offset)
        return [AnalysisListItem.model_validate(r) for r in runs]

    async def delete(self, analysis_id: uuid.UUID) -> None:
        run = await self.analysis_repo.get(analysis_id)
        if run is None:
            raise NotFoundProblem(detail="Run not found.")
        logger.info("deleting analysis %s", str(analysis_id)[:8])
        await self.analysis_repo.delete(run)

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
        stp_compound_id: uuid.UUID | None = None,
        stp_target_ids: list[uuid.UUID] | None = None,
    ) -> None:
        """Apply a durable in-stage entity edit (add/remove) and stage the change.

        Validates added ids exist, enforces the entity cap on net additions, folds the edit into
        the durable edit layer, and re-derives the edited stage's stored result. An edit may never
        empty a stage: removing the last remaining entity is rejected (422) and nothing is
        persisted. Otherwise it persists the edit, flags produced downstream stages stale, and
        records ``parameters.rerun_from``; nothing is re-run (D3). Recompute happens only on an
        explicit reset-from.
        """
        stp_target_ids = stp_target_ids or []
        if stp_compound_id is not None or stp_target_ids:
            if stage != 3:
                raise ValidationProblem(
                    detail="SwissTargetPrediction links can only be attached to Stage 3."
                )
            if stp_compound_id is None or not stp_target_ids:
                raise ValidationProblem(
                    detail=(
                        "SwissTargetPrediction imports require one compound and at "
                        "least one target."
                    )
                )

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

        # Verify ids exist. STP target ids may include targets that are already in the run,
        # so validate the union while still applying the edit layer only to fresh additions.
        ids_to_verify = list(dict.fromkeys([*add, *stp_target_ids]))
        if ids_to_verify:
            existing_ids = await repo.existing_ids(ids_to_verify)
            missing = [c for c in ids_to_verify if c not in existing_ids]
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

        # Resolve added entities through the shared edit entries so manual rows
        # carry the same identity/link fields as prefilled or computed rows.
        add_entries: list[dict[str, Any]] = []
        if add:
            for obj in await repo.get_many(add):
                if entity == "target":
                    add_entries.append(self._target_add_entry(obj))
                else:
                    add_entries.append(self._compound_add_entry(obj))

        # Fold into the durable edit layer (computed; not yet persisted).
        prior_edit = run.parameters.get("stage_edits", {}).get(skey, edits.empty_edit())
        new_edit = edits.normalize_edit(
            prior_edit, add_entries, [str(r) for r in remove], id_key=id_key
        )

        # Re-derive the edited stage's stored result from its computed entities + new edit.
        # Preserve EVERY field the runner attached to each computed row (Stage 4 carries the
        # disease association score / type / source_url; Stage 3/4 carry gene_symbol /
        # uniprot_accession) so an edit never strips them — Stage 5/6 read the score and
        # Stage 8 reads gene_symbol off this list (B-DUP-2/L-11). The `tag` is re-derived by
        # build_stage_entities, so drop the stored one.
        computed_ids = existing_result["computed_ids"]
        by_id = {c[id_key]: c for c in existing_result[list_key]}
        computed_entities: list[dict[str, Any]] = []
        for cid in computed_ids:
            row = {k: v for k, v in by_id.get(cid, {}).items() if k != "tag"}
            row[id_key] = cid
            row.setdefault("canonical_name", None)
            computed_entities.append(row)
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
        result = {**preserved, **frag}
        if stage == 3 and stp_compound_id is not None:
            self._apply_stp_run_links(
                result,
                compound_id=str(stp_compound_id),
                target_ids=[str(tid) for tid in stp_target_ids],
            )
        await self.analysis_repo.set_stage_result(run, stage, result)

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
