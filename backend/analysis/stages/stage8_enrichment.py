import logging
from collections import defaultdict
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from integrations.gprofiler import run_enrichment
from integrations._retry import ServiceUnavailableError

logger = logging.getLogger(__name__)


def _group_by_source(results) -> dict:
    grouped = {}
    for r in results:
        source = r.source
        if source not in grouped:
            grouped[source] = []
        grouped[source].append({
            "term_id": r.term_id,
            "term_name": r.term_name,
            "fdr": round(r.fdr, 8),
            "intersection_size": r.intersection_size,
            "term_size": r.term_size,
            "genes": r.genes,
        })
    for source in grouped:
        grouped[source] = sorted(grouped[source], key=lambda x: x["fdr"])[:20]
    return grouped


def _empty_enrichment(hub_genes: list[str], degraded: bool = False, reason: str | None = None) -> dict:
    result = {
        "total_significant": 0,
        "go_bp": [], "go_mf": [], "go_cc": [], "kegg": [],
        "hub_genes_queried": hub_genes,
        "communities": [],
        "global_enrichment": {
            "go_bp": [], "go_mf": [], "go_cc": [], "kegg": [],
            "hub_genes_queried": hub_genes,
        },
    }
    if degraded:
        result["degraded"] = True
        result["warning"] = {"provider": "g:Profiler", "reason": reason or "service unavailable"}
    return result


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage7 = (run.stage_results or {}).get("stage_7", {})
    ranked = stage7.get("ranked", [])
    hub_genes = [r["gene_symbol"] for r in ranked]

    if not hub_genes:
        return _empty_enrichment([])

    # Background: ALL compound targets from Stage 3 — the study protein space.
    # Using the full compound target universe (not just Stage 5 overlap genes) is the
    # scientifically correct background for enrichment: it represents all proteins the
    # compound set has been screened against, giving a meaningful reference universe.
    # Using the small overlap set (~10-50 genes) as background inflates significance
    # because hub genes are a large fraction of a tiny denominator.
    # Cite: Rivals et al. 2007 (Bioinformatics 23:401) — background set methodology.
    stage3 = (run.stage_results or {}).get("stage_3", {})
    background = stage3.get("target_gene_symbols") or None  # list[str] of gene symbols

    try:
        # Overall enrichment (all hub genes — preserved for backward compatibility)
        results = await run_enrichment(
            gene_symbols=hub_genes,
            sources=config.enrichment.sources,
            fdr_threshold=config.enrichment.fdr_threshold,
            background=background,
        )
        grouped = _group_by_source(results)

        # Per-community enrichment
        # Group hub genes by community_id (default 0 if missing)
        community_genes: dict[int, list[str]] = defaultdict(list)
        for r in ranked:
            comm_id = r.get("community_id", 0)
            community_genes[comm_id].append(r["gene_symbol"])

        community_results = []
        for comm_id in sorted(community_genes.keys()):
            genes = community_genes[comm_id]
            if len(genes) < 3:
                # Skip tiny communities — insufficient gene count for meaningful ORA
                continue
            comm_enrichment = await run_enrichment(
                gene_symbols=genes,
                sources=config.enrichment.sources,
                fdr_threshold=config.enrichment.fdr_threshold,
                background=background,
            )
            comm_grouped = _group_by_source(comm_enrichment)
            community_results.append({
                "community_id": comm_id,
                "gene_count": len(genes),
                "genes": genes,
                "go_bp": comm_grouped.get("GO:BP", []),
                "go_mf": comm_grouped.get("GO:MF", []),
                "go_cc": comm_grouped.get("GO:CC", []),
                "kegg": comm_grouped.get("KEGG", []),
            })

        # Global enrichment — all hub genes combined, deduplicated
        all_hub_genes = list(dict.fromkeys(
            gene_symbol
            for community_genes_list in community_genes.values()
            for gene_symbol in community_genes_list
        ))

        if all_hub_genes:
            global_results = await run_enrichment(
                gene_symbols=all_hub_genes,
                sources=config.enrichment.sources,
                fdr_threshold=config.enrichment.fdr_threshold,
                background=background,
            )
            global_grouped = _group_by_source(global_results)
        else:
            global_grouped = {}

        return {
            "total_significant": len(results),
            "go_bp": grouped.get("GO:BP", []),
            "go_mf": grouped.get("GO:MF", []),
            "go_cc": grouped.get("GO:CC", []),
            "kegg": grouped.get("KEGG", []),
            "hub_genes_queried": hub_genes,
            "communities": community_results,
            "global_enrichment": {
                "go_bp": global_grouped.get("GO:BP", []),
                "go_mf": global_grouped.get("GO:MF", []),
                "go_cc": global_grouped.get("GO:CC", []),
                "kegg": global_grouped.get("KEGG", []),
                "hub_genes_queried": all_hub_genes,
            },
        }
    except ServiceUnavailableError as exc:
        logger.warning("Stage 8 degraded — g:Profiler unavailable: %s", exc)
        return _empty_enrichment(hub_genes, degraded=True, reason=str(exc))
