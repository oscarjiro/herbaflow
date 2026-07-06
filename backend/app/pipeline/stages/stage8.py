"""Stage 8 — Functional enrichment (GO + KEGG via g:Profiler). TERMINAL stage.

Turn the Stage-5 overlap gene list into a mechanistic read-out: which GO terms + KEGG pathways
the overlap is over-represented in, tested against the **Stage-3 compound-target universe** as
the custom statistical background (Methodology §8.4; Wijesooriya 2022). One external API
(g:Profiler), via the verified REST client. The terminal interpretive output — on completion the
engine marks the run ``complete``.

Reads ``stage_results["5"].overlap`` (query gene symbols) + ``stage_results["3"].targets``
(background gene symbols, hardcoded custom — EN-2). Both drop null gene symbols so query and
background are measured in the same namespace (query ⊆ background, overlap ⊆ S3).

Resilience (EN-5): empty query -> honest null (``empty_input``); g:Profiler outage -> DEGRADE
(``source_degraded``), the run STILL completes. ``min_term_size`` is filtered client-side
(g:Profiler has no such param). ``terms[*].intersection`` carries the query genes per term (feeds
Phase-4 C-T-P pathway edges; ``intersection_size`` is always present even if the gene list is not).

Result fragment (``stage_results["8"]``); ``count`` = number of enriched terms (0 is a valid
honest null, NOT an empty-gate stop — the engine exempts stages 7/8):
  - ``terms``: [{source, term_id, name, p_value, term_size, query_size, intersection_size,
                intersection}]
  - ``input_gene_count`` / ``background_gene_count`` / ``background_source`` / ``correction`` /
    ``significance_threshold`` / ``min_term_size`` / ``sources`` / ``degraded`` / ``flags``
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.gprofiler import EnrichedTerm, GprofilerClient, GprofilerError
from app.pipeline.genes import distinct_gene_symbols

logger = logging.getLogger("herbaflow.pipeline")


async def compute(
    stage5: dict[str, Any],
    stage3: dict[str, Any],
    *,
    client: Any,
    significance_threshold: float,
    sources: list[str],
    correction: str,
    min_term_size: int,
    no_iea: bool = False,
) -> dict[str, Any]:
    """Assemble query + custom background, call g:Profiler, filter, shape. Degrade on outage."""
    query = distinct_gene_symbols(stage5.get("overlap", []))
    background = distinct_gene_symbols(stage3.get("targets", []))

    base = {
        "input_gene_count": len(query),
        "background_gene_count": len(background),
        "background_source": "compound_target_universe",
        "correction": correction,
        "significance_threshold": significance_threshold,
        "min_term_size": min_term_size,
        "sources": sources,
        "no_iea": no_iea,
        "state": "computed",
    }

    if not query:
        return {**base, "terms": [], "count": 0, "degraded": False, "flags": ["empty_input"]}

    try:
        terms: list[EnrichedTerm] = await client.profile(
            query=query,
            background=background,
            sources=sources,
            correction=correction,
            user_threshold=significance_threshold,
            no_iea=no_iea,
        )
    except GprofilerError:
        logger.warning("stage 8: g:Profiler degraded — completing with no terms")
        return {**base, "terms": [], "count": 0, "degraded": True, "flags": ["source_degraded"]}

    kept = [
        {
            "source": t.source,
            "term_id": t.native,
            "name": t.name,
            "p_value": t.p_value,
            "term_size": t.term_size,
            "query_size": t.query_size,
            "intersection_size": t.intersection_size,
            "intersection": t.intersection,
        }
        for t in terms
        if t.term_size >= min_term_size
    ]
    flags: list[str] = []
    if not kept:
        flags.append("no_enriched_terms")
    return {**base, "terms": kept, "count": len(kept), "degraded": False, "flags": flags}


async def run(
    session: AsyncSession | None, run: Any, *, client: Any | None = None
) -> dict[str, Any]:
    """Enrich the run's Stage-5 overlap against its Stage-3 universe.

    ``session`` is accepted for symmetry with other stage runners; it is unused here.
    """
    stage5 = run.stage_results["5"]
    stage3 = run.stage_results["3"]
    params = run.parameters["enrichment"]

    async def _go(enrichment_client: Any) -> dict[str, Any]:
        return await compute(
            stage5,
            stage3,
            client=enrichment_client,
            significance_threshold=float(params["significance_threshold"]),
            sources=list(params["sources"]),
            correction=str(params["correction"]),
            min_term_size=int(params["min_term_size"]),
            no_iea=bool(params.get("no_iea", False)),
        )

    if client is not None:
        result = await _go(client)
    else:
        async with httpx.AsyncClient() as http:
            result = await _go(GprofilerClient(http))
    logger.info(
        "stage 8: %d term(s) for %d query / %d background genes (degraded=%s)",
        result["count"],
        result["input_gene_count"],
        result["background_gene_count"],
        result["degraded"],
    )
    return result
