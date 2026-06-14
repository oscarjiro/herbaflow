"""Results-handoff orchestration: load a complete run, batch-fetch entity attributes, and call
the pure builders in ``app.pipeline.results_handoff``. The only place export touches the DB."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import ConflictProblem, NotFoundProblem
from app.pipeline import charts, report, state
from app.pipeline import results_handoff as rh
from app.repositories.analysis import AnalysisRepository
from app.repositories.compound import CompoundRepository
from app.repositories.disease import DiseaseRepository
from app.repositories.plant import PlantRepository
from app.repositories.target import TargetRepository


@dataclass(frozen=True)
class ExportArtifacts:
    report: str
    stage_csvs: dict[int, str]
    ctp_nodes: str
    ctp_edges: str
    ppi_nodes: str
    ppi_edges: str
    docking: str
    network_png: bytes | None = None
    stage_pngs: dict[str, bytes] = field(default_factory=dict)

    def _network_files(self) -> dict[str, str | bytes | None]:
        return {
            "ctp-nodes.csv": self.ctp_nodes,
            "ctp-edges.csv": self.ctp_edges,
            "docking.csv": self.docking,
            "ctp-network.png": self.network_png,
        }

    def _stage_files(self) -> dict[str, str | bytes | None]:
        slug = report.STAGE_CSV_SLUG
        files: dict[str, str | bytes | None] = {
            f"stage{n}_{slug[n]}.csv": csv for n, csv in self.stage_csvs.items()
        }
        files["stage6_ppi_nodes.csv"] = self.ppi_nodes
        files.update(self.stage_pngs)  # e.g. stage5_venn.png -> bytes (wired in a later task)
        return files

    def network_bundle(self) -> bytes:
        return rh.build_network_bundle(
            ctp_nodes=self.ctp_nodes,
            ctp_edges=self.ctp_edges,
            docking=self.docking,
            network_png=self.network_png,
            readme=rh.build_network_readme(),
        )

    def stages_bundle(self) -> bytes:
        return rh.build_stages_bundle(
            stage_files=self._stage_files(), readme=rh.build_stages_readme()
        )

    def all_results_bundle(self) -> bytes:
        return rh.build_all_results_bundle(
            report=self.report,
            network_files=self._network_files(),
            stage_files=self._stage_files(),
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
    params = run.parameters or {}
    input_modes = params.get("input_modes") or {}

    ctp_graph = rh.build_ctp_graph(sr, compounds_by_id, targets_by_id)
    ppi_graph = rh.build_ppi_graph(sr)
    network_png = charts.render_network(ctp_graph, title="Compound-target-pathway network")
    stage_pngs: dict[str, bytes] = {}
    if (venn := charts.render_venn(sr.get("5", {}))) is not None:
        stage_pngs["stage5_venn.png"] = venn
    if (ppi := charts.render_network(ppi_graph, title="PPI network")) is not None:
        stage_pngs["stage6_ppi_network.png"] = ppi
    if (bar := charts.render_hub_bar(sr.get("7", {}))) is not None:
        stage_pngs["stage7_hub_bar.png"] = bar
    overlap_size = sr.get("5", {}).get("count")
    for cat in charts.ENRICHMENT_CATEGORIES:
        png = charts.render_enrichment_bubble(sr.get("8", {}), cat, overlap_size=overlap_size)
        if png is not None:
            stage_pngs[f"stage8_enrichment_{charts.category_slug(cat)}.png"] = png

    figures: list[tuple[str, bool, str]] = [
        ("ctp-network.png", network_png is not None, "sparse C-T-P network (no edges)"),
        ("stage5_venn.png", "stage5_venn.png" in stage_pngs, "empty overlap"),
        (
            "stage6_ppi_network.png",
            "stage6_ppi_network.png" in stage_pngs,
            "sparse or empty PPI network",
        ),
        ("stage7_hub_bar.png", "stage7_hub_bar.png" in stage_pngs, "no hub genes"),
    ]
    for cat in charts.ENRICHMENT_CATEGORIES:
        fn = f"stage8_enrichment_{charts.category_slug(cat)}.png"
        figures.append((fn, fn in stage_pngs, f"no enriched terms in {cat}"))

    return ExportArtifacts(
        report=rh.build_report(
            run_meta,
            params,
            sr,
            labels,
            input_modes=input_modes,
            frontend_url=settings.frontend_url,
            figures=figures,
        ),
        stage_csvs={
            n: rh.build_stage_csv(n, sr, compounds_by_id, targets_by_id) for n in range(1, 9)
        },
        ctp_nodes=rh.build_ctp_nodes(sr, compounds_by_id, targets_by_id),
        ctp_edges=rh.build_ctp_edges(sr, compounds_by_id, targets_by_id),
        ppi_nodes=rh.build_ppi_nodes(sr),
        ppi_edges=rh.build_ppi_edges(sr),
        docking=rh.build_docking_table(sr, compounds_by_id, targets_by_id),
        network_png=network_png,
        stage_pngs=stage_pngs,
    )
