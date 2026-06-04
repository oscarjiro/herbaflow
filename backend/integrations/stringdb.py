import logging
import httpx
from dataclasses import dataclass

from integrations._retry import with_retry, ServiceUnavailableError

logger = logging.getLogger(__name__)

STRING_BASE = "https://string-db.org/api/json"
SPECIES_HUMAN = 9606


@dataclass
class PpiEdgeData:
    gene_a: str
    gene_b: str
    combined_score: float
    experimental_score: float
    textmining_score: float
    coexpression_score: float


async def get_ppi_network(
    gene_symbols: list[str],
    min_confidence: float = 0.4,
) -> list[PpiEdgeData]:
    """
    Fetch PPI edges for gene symbols from STRING DB.
    min_confidence: 0.15=low, 0.40=medium, 0.70=high, 0.90=highest
    STRING uses 0-1000 scale internally; we convert.
    """
    if not gene_symbols:
        return []

    identifiers = "\r".join(gene_symbols)
    params = {
        "identifiers": identifiers,
        "species": SPECIES_HUMAN,
        "required_score": int(min_confidence * 1000),
        "caller_identity": "herbaflow_thesis",
        "format": "json",
    }

    async with httpx.AsyncClient() as client:
        try:
            async def _fetch_string() -> httpx.Response:
                r = await client.post(
                    f"{STRING_BASE}/network",
                    data=params,
                    timeout=60,
                )
                r.raise_for_status()
                return r

            resp = await with_retry(_fetch_string, service_name="STRING-DB")
        except ServiceUnavailableError:
            logger.error("STRING-DB unavailable after retries for %d genes", len(gene_symbols))
            raise
        except httpx.HTTPError as exc:
            logger.error("STRING-DB HTTP error for %d genes: %s", len(gene_symbols), exc)
            return []

    edges = []
    for row in resp.json():
        gene_a = row.get("preferredName_A", "")
        gene_b = row.get("preferredName_B", "")
        if not gene_a or not gene_b or gene_a == gene_b:
            continue
        combined = float(row.get("score", 0))
        if combined < min_confidence:
            continue
        edges.append(PpiEdgeData(
            gene_a=gene_a.upper(),
            gene_b=gene_b.upper(),
            combined_score=combined,
            experimental_score=float(row.get("escore", 0)),
            textmining_score=float(row.get("tscore", 0)),
            # STRING's JSON network API names coexpression "ascore"
            # (escore=experimental, tscore=textmining, ascore=coexpression).
            coexpression_score=float(row.get("ascore", 0)),
        ))

    return edges
