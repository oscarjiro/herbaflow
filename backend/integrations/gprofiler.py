import logging
from dataclasses import dataclass

import httpx

from integrations._retry import ServiceUnavailableError, with_retry

logger = logging.getLogger(__name__)

GPROFILER_BASE = "https://biit.cs.ut.ee/gprofiler/api"


@dataclass
class EnrichmentResult:
    source: str          # 'GO:BP', 'GO:MF', 'GO:CC', 'KEGG'
    term_id: str
    term_name: str
    fdr: float
    intersection_size: int
    term_size: int
    query_size: int
    genes: list[str]


async def run_enrichment(
    gene_symbols: list[str],
    sources: list[str] | None = None,
    fdr_threshold: float = 0.05,
    organism: str = "hsapiens",
    background: list[str] | None = None,
    significance_threshold_method: str = "fdr",
) -> list[EnrichmentResult]:
    """Run GO and KEGG enrichment via g:Profiler. Returns results with fdr <= fdr_threshold.

    Args:
        background: Custom statistical background gene set. When provided, g:Profiler
            uses only these genes as the reference universe instead of the full genome.
            Standard for NP network pharmacology: pass ALL compound targets (Stage 3
            target_gene_symbols) as the study protein space.
            (Rivals et al. 2007, Bioinformatics 23:401)
        significance_threshold_method: Multiple-testing correction method passed to
            g:Profiler. Defaults to "fdr" = Benjamini-Hochberg false discovery rate
            (Benjamini & Hochberg 1995, J. R. Statist. Soc. B 57:289), rather than
            g:Profiler's native "g_SCS" default. BH is the de-facto standard correction
            reported across network-pharmacology enrichment studies, so our reported
            FDRs stay directly comparable to published reference datasets. g:Profiler
            also accepts "g_SCS" and "bonferroni". (Raudvere et al. 2019, NAR 47:W191)
    """
    if not gene_symbols:
        return []

    if sources is None:
        sources = ["GO:BP", "GO:MF", "GO:CC", "KEGG"]

    payload = {
        "organism": organism,
        "query": gene_symbols,
        "sources": sources,
        "user_threshold": fdr_threshold,
        "significance_threshold_method": significance_threshold_method,
        "domain_scope": "custom_annotated" if background else "annotated",
        "no_evidences": False,
    }
    if background:
        payload["background"] = background

    async with httpx.AsyncClient() as client:
        try:
            async def _fetch_gprofiler() -> httpx.Response:
                r = await client.post(
                    f"{GPROFILER_BASE}/gost/profile/",
                    json=payload,
                    timeout=60,
                )
                r.raise_for_status()
                return r

            resp = await with_retry(_fetch_gprofiler, service_name="g:Profiler")
        except ServiceUnavailableError:
            logger.error("g:Profiler unavailable after retries for %d genes", len(gene_symbols))
            raise
        except httpx.HTTPError as exc:
            logger.error("g:Profiler HTTP error for %d genes: %s", len(gene_symbols), exc)
            return []

    data = resp.json()
    results_raw = data.get("result", [])

    # With no_evidences=False, intersections is parallel to the query list:
    # intersections[i] is non-empty iff gene_symbols[i] hits this term.
    def _extract_genes(intersections: list) -> list[str]:
        return [
            gene_symbols[i]
            for i, ev in enumerate(intersections)
            if ev and i < len(gene_symbols)
        ]

    results = []
    for row in results_raw:
        if row.get("significant") is False:
            continue
        # g:Profiler returns the BH-corrected significance in its "p_value" field
        # and does not return a separate raw p-value; we store it as fdr.
        fdr = row.get("p_value", 1.0)
        if fdr > fdr_threshold:
            continue
        results.append(EnrichmentResult(
            source=row.get("source", ""),
            term_id=row.get("native", ""),
            term_name=row.get("name", ""),
            fdr=fdr,
            intersection_size=row.get("intersection_size", 0),
            term_size=row.get("term_size", 0),
            query_size=row.get("query_size", 0),
            genes=_extract_genes(row.get("intersections", [])),
        ))

    return results
