"""Results-handoff orchestration: load a complete run, batch-fetch entity attributes, and call
the pure builders in ``app.pipeline.results_handoff``. The only place export touches the DB."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictProblem, NotFoundProblem
from app.pipeline import results_handoff as rh
from app.pipeline import state
from app.repositories.analysis import AnalysisRepository
from app.repositories.compound import CompoundRepository
from app.repositories.disease import DiseaseRepository
from app.repositories.plant import PlantRepository
from app.repositories.target import TargetRepository


@dataclass(frozen=True)
class ExportArtifacts:
    ctp_nodes: str
    ctp_edges: str
    docking: str
    report: str

    def bundle(self) -> bytes:
        return rh.build_bundle(
            ctp_nodes=self.ctp_nodes,
            ctp_edges=self.ctp_edges,
            docking=self.docking,
            report=self.report,
        )


def _uuids(ids: set[str]) -> list[uuid.UUID]:
    out: list[uuid.UUID] = []
    for i in ids:
        try:
            out.append(uuid.UUID(str(i)))
        except (ValueError, AttributeError):
            continue
    return out


async def _resolve_labels(session: AsyncSession, run: Any) -> dict[str, Any]:
    """B4 opaque display labels (may be N/A). Prefer the run's stored ``labels`` (manual entry);
    otherwise resolve the selected plant(s)/disease name from the catalog. Never assume an id
    exists — labels may legitimately be ``None`` so the report prints N/A."""
    params: dict[str, Any] = run.parameters or {}
    stored = params.get("labels") or {}
    plant = stored.get("plant")
    disease = stored.get("disease")

    if plant is None:
        plant_ids = {str(p) for p in (params.get("plant_ids") or [])}
        if plant_ids:
            plants = await PlantRepository(session).list_all()
            names = [
                p.canonical_scientific_name
                for p in plants
                if str(p.plant_id) in plant_ids and p.canonical_scientific_name
            ]
            plant = ", ".join(names) if names else None

    if disease is None and getattr(run, "disease_id", None):
        diseases = await DiseaseRepository(session).list_all()
        disease = next(
            (d.disease_name for d in diseases if d.disease_id == run.disease_id),
            None,
        )

    return {"plant": plant, "disease": disease}


async def assemble_export(session: AsyncSession, analysis_id: uuid.UUID) -> ExportArtifacts:
    run = await AnalysisRepository(session).get(analysis_id)
    if run is None:
        raise NotFoundProblem(f"analysis {analysis_id} not found")
    if run.status != state.COMPLETE:
        raise ConflictProblem("export is available only when the run is complete")

    sr: dict[str, Any] = run.stage_results or {}
    edges = sr.get("3", {}).get("compound_targets", [])
    compound_ids = {e["compound_id"] for e in edges}
    target_ids = (
        {o["target_id"] for o in sr.get("5", {}).get("overlap", [])}
        | {h["target_id"] for h in sr.get("7", {}).get("hubs", [])}
        | {e["target_id"] for e in edges}
    )

    compounds = await CompoundRepository(session).get_many(_uuids(compound_ids))
    targets = await TargetRepository(session).get_many(_uuids(target_ids))
    compounds_by_id = {
        str(c.compound_id): {
            "name": c.canonical_name,
            "inchi_key": c.inchi_key,
            "smiles": c.smiles,
        }
        for c in compounds
    }
    targets_by_id = {
        str(t.target_id): {
            "gene_symbol": t.gene_symbol,
            "uniprot_accession": t.uniprot_accession,
        }
        for t in targets
    }
    labels = await _resolve_labels(session, run)
    run_meta = {
        "analysis_id": str(run.analysis_id),
        "name": run.analysis_name,
        "mode": run.mode,
        "created_at": str(run.created_at),
        "completed_at": str(run.completed_at),
    }
    return ExportArtifacts(
        ctp_nodes=rh.build_ctp_nodes(sr, compounds_by_id, targets_by_id),
        ctp_edges=rh.build_ctp_edges(sr),
        docking=rh.build_docking_table(sr, compounds_by_id, targets_by_id),
        report=rh.build_report(run_meta, run.parameters or {}, sr, labels),
    )
