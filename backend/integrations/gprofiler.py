import httpx
from dataclasses import dataclass

GPROFILER_BASE = "https://biit.cs.ut.ee/gprofiler/api"


@dataclass
class EnrichmentResult:
    source: str          # 'GO:BP', 'GO:MF', 'GO:CC', 'KEGG'
    term_id: str
    term_name: str
    p_value: float
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
) -> list[EnrichmentResult]:
    """Run GO and KEGG enrichment via g:Profiler. Returns results with fdr <= fdr_threshold.

    Args:
        background: Custom statistical background gene set. When provided, g:Profiler
            uses only these genes as the reference universe instead of the full genome.
            Standard for NP network pharmacology: pass Stage 5 overlap genes.
            (Tang et al. 2022, Ru et al. 2019)
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
        "domain_scope": "annotated",
        "no_evidences": False,
    }
    if background:
        payload["background"] = background

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{GPROFILER_BASE}/gost/profile/",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

    data = resp.json()
    results_raw = data.get("result", [])

    results = []
    for row in results_raw:
        if row.get("significant") is False:
            continue
        fdr = row.get("p_value", 1.0)
        if fdr > fdr_threshold:
            continue
        results.append(EnrichmentResult(
            source=row.get("source", ""),
            term_id=row.get("native", ""),
            term_name=row.get("name", ""),
            p_value=row.get("p_value", 1.0),
            fdr=fdr,
            intersection_size=row.get("intersection_size", 0),
            term_size=row.get("term_size", 0),
            query_size=row.get("query_size", 0),
            genes=row.get("intersections", []),
        ))

    return results
