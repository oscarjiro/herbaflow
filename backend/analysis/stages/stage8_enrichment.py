from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from integrations.gprofiler import run_enrichment


def _group_by_source(results) -> dict:
    grouped = {}
    for r in results:
        source = r.source
        if source not in grouped:
            grouped[source] = []
        grouped[source].append({
            "term_id": r.term_id,
            "term_name": r.term_name,
            "p_value": round(r.p_value, 8),
            "fdr": round(r.fdr, 8),
            "intersection_size": r.intersection_size,
            "term_size": r.term_size,
            "genes": r.genes,
        })
    for source in grouped:
        grouped[source] = sorted(grouped[source], key=lambda x: x["fdr"])[:20]
    return grouped


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage7 = (run.stage_results or {}).get("stage_7", {})
    hub_genes = [r["gene_symbol"] for r in stage7.get("hub_genes", [])]

    if not hub_genes:
        return {"total_significant": 0, "go_bp": [], "go_mf": [], "go_cc": [], "kegg": []}

    results = await run_enrichment(
        gene_symbols=hub_genes,
        sources=config.enrichment.sources,
        fdr_threshold=config.enrichment.fdr_threshold,
    )

    grouped = _group_by_source(results)
    return {
        "total_significant": len(results),
        "go_bp": grouped.get("GO:BP", []),
        "go_mf": grouped.get("GO:MF", []),
        "go_cc": grouped.get("GO:CC", []),
        "kegg": grouped.get("KEGG", []),
        "hub_genes_queried": hub_genes,
    }
