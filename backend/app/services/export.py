"""Results-handoff orchestration: load a complete run, batch-fetch entity attributes, and call
the pure builders in ``app.pipeline.results_handoff``. The only place export touches the DB."""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import ConflictProblem, NotFoundProblem
from app.pipeline import charts, entry_modes, report, state
from app.pipeline import results_handoff as rh
from app.pipeline.results_handoff import ctp_is_emittable
from app.repositories.analysis import AnalysisRepository
from app.repositories.compound import CompoundRepository
from app.repositories.disease import DiseaseRepository
from app.repositories.plant import PlantRepository
from app.repositories.target import TargetRepository
from app.schemas.graph import CtpGraph


@dataclass(frozen=True)
class ExportArtifacts:
    report: str
    stage_csvs: dict[int, str]
    ctp_nodes: str
    ctp_edges: str
    ppi_nodes: str
    ppi_edges: str
    slug: str = "herbaflow_analysis"
    network_png: bytes | None = None
    stage_pngs: dict[str, bytes] = field(default_factory=dict)
    input_modes: dict[str, Any] = field(default_factory=dict)
    has_compounds: bool = True
    stage_results: dict[str, Any] = field(default_factory=dict)

    def _ctp_emittable(self) -> bool:
        return ctp_is_emittable(self.stage_results, has_compounds=self.has_compounds)

    def _network_files(self) -> dict[str, str | bytes | None]:
        if not self._ctp_emittable():
            return {}
        return {
            "ctp-nodes.csv": self.ctp_nodes,
            "ctp-edges.csv": self.ctp_edges,
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

    def network_bundle(self) -> bytes | None:
        """Returns None when C-T-P is not emittable (router must 404 in that case)."""
        if not self._ctp_emittable():
            return None
        return rh.build_network_bundle(
            ctp_nodes=self.ctp_nodes,
            ctp_edges=self.ctp_edges,
            network_png=self.network_png,
            readme=rh.build_network_readme(),
        )

    def stages_bundle(self) -> bytes:
        return rh.build_stages_bundle(
            stage_files=self._stage_files(),
            readme=rh.build_stages_readme(),
            input_modes=self.input_modes,
        )

    def all_results_bundle(self) -> bytes:
        return rh.build_all_results_bundle(
            report=self.report,
            network_files=self._network_files(),
            stage_files=self._stage_files(),
            input_modes=self.input_modes,
        )


def _ppi_figure(
    sr: dict[str, Any],
    ppi_graph: dict[str, Any],
    *,
    hub_scores: dict[str, float],
    min_confidence: float,
) -> bytes | None:
    """The PPI figure for the bundle. Prefer STRING's stored server-rendered image
    (sr["6"].network_image, base64); on its absence or a decode error fall back to the
    local matplotlib render. Export makes NO network call — it only reads stored bytes."""
    stored = (sr.get("6") or {}).get("network_image")
    if stored:
        try:
            return base64.b64decode(stored)
        except (ValueError, TypeError):
            pass
    return charts.render_ppi_network(
        ppi_graph, hub_scores=hub_scores, min_confidence=min_confidence
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


async def _load_ctp_lookups(
    session: AsyncSession, run: Any
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]], bool]:
    """Batch-fetch the entity-attribute lookups the C-T-P graph builder needs from a complete run.

    The SINGLE home for the export lookup build: gathers compound/target ids from the run's
    ``stage_results``, batch-fetches via ``CompoundRepository.get_many`` / ``TargetRepository``,
    and returns ``(stage_results, compounds_by_id, targets_by_id, has_compounds)``. Shared by
    ``assemble_export`` (the download artifacts) and ``assemble_ctp_graph`` (the JSON endpoint) so
    there is no second copy of the lookup-build logic (one canonical home rule)."""
    sr: dict[str, Any] = run.stage_results or {}
    edges = sr.get("3", {}).get("compound_targets", [])
    stage1_compound_ids = {
        c["compound_id"] for c in sr.get("1", {}).get("compounds", []) if c.get("compound_id")
    }
    stage2_compound_ids = {
        c["compound_id"]
        for bucket in ("passed", "filtered")
        for c in sr.get("2", {}).get(bucket, [])
        if c.get("compound_id")
    }
    compound_ids = {e["compound_id"] for e in edges} | stage1_compound_ids | stage2_compound_ids
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
    has_compounds = entry_modes.has_compounds_from_params(run.parameters or {})
    return sr, compounds_by_id, targets_by_id, has_compounds


async def assemble_ctp_graph(session: AsyncSession, analysis_id: uuid.UUID) -> CtpGraph:
    """Assemble the compound-target-pathway graph for a complete run as a typed DTO.

    Reuses the single graph-data home (``results_handoff.build_ctp_graph``) and the shared
    ``_load_ctp_lookups`` batch-fetch — no second copy of either the graph logic or the lookup
    build. Compound-free runs (``manual_targets``) get an empty graph. The only DB touch for the
    JSON endpoint."""
    run = await AnalysisRepository(session).get(analysis_id)
    if run is None:
        raise NotFoundProblem(f"analysis {analysis_id} not found")
    if run.status != state.COMPLETE:
        raise ConflictProblem("the C-T-P graph is available only when the run is complete")

    sr, compounds_by_id, targets_by_id, has_compounds = await _load_ctp_lookups(session, run)
    graph = rh.build_ctp_graph(sr, compounds_by_id, targets_by_id, has_compounds=has_compounds)
    return CtpGraph.model_validate(graph)


async def assemble_export(session: AsyncSession, analysis_id: uuid.UUID) -> ExportArtifacts:
    run = await AnalysisRepository(session).get(analysis_id)
    if run is None:
        raise NotFoundProblem(f"analysis {analysis_id} not found")
    if run.status != state.COMPLETE:
        raise ConflictProblem("export is available only when the run is complete")

    sr, compounds_by_id, targets_by_id, has_compounds = await _load_ctp_lookups(session, run)
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

    ctp_emittable = ctp_is_emittable(sr, has_compounds=has_compounds)
    ctp_graph = (
        rh.build_ctp_graph(sr, compounds_by_id, targets_by_id, has_compounds=has_compounds)
        if ctp_emittable
        else {"nodes": [], "edges": []}
    )
    ppi_graph = rh.build_ppi_graph(sr)
    network_png = charts.render_ctp_network(ctp_graph) if ctp_emittable else None
    stage_pngs: dict[str, bytes] = {}
    venn = charts.render_venn(
        sr.get("5", {}),
        plant_label=labels.get("plant"),
        disease_label=labels.get("disease"),
    )
    if venn is not None:
        stage_pngs["stage5_venn.png"] = venn
    # float() not int: MCC scores are large Python ints on dense graphs and matplotlib's node/bar
    # colour conversion overflows beyond C-long range; the score here only drives display colour.
    hub_scores = {
        h["gene_symbol"]: float(h.get("mcc") or 0.0) for h in sr.get("7", {}).get("hubs", [])
    }
    min_confidence = (params.get("ppi") or {}).get("min_confidence", 0.4)
    ppi = _ppi_figure(sr, ppi_graph, hub_scores=hub_scores, min_confidence=min_confidence)
    if ppi is not None:
        stage_pngs["stage6_ppi_network.png"] = ppi
    if (bar := charts.render_hub_bar(sr.get("7", {}))) is not None:
        stage_pngs["stage7_hub_bar.png"] = bar
    overlap_size = sr.get("5", {}).get("count")
    for cat in charts.ENRICHMENT_CATEGORIES:
        png = charts.render_enrichment_bubble(sr.get("8", {}), cat, overlap_size=overlap_size)
        if png is not None:
            stage_pngs[f"stage8_enrichment_{charts.category_slug(cat)}.png"] = png

    figures: list[tuple[str, bool, str]] = []
    if ctp_emittable:
        figures.append(
            ("ctp-network.png", network_png is not None, "sparse C-T-P network (no edges)")
        )
    figures += [
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
        ctp_nodes=(rh.build_ctp_nodes(sr, compounds_by_id, targets_by_id) if ctp_emittable else ""),
        ctp_edges=(rh.build_ctp_edges(sr, compounds_by_id, targets_by_id) if ctp_emittable else ""),
        ppi_nodes=rh.build_ppi_nodes(sr),
        ppi_edges=rh.build_ppi_edges(sr),
        slug=rh.bundle_slug(labels, run.completed_at),
        network_png=network_png,
        stage_pngs=stage_pngs,
        input_modes=input_modes,
        has_compounds=has_compounds,
        stage_results=sr,
    )
