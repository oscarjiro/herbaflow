"""g:Profiler client — functional enrichment (GO + KEGG) of the overlap gene list.

Written to the verified g:Profiler REST contract (biit.cs.ut.ee/gprofiler/page/apis, 2026-06-11):
POST /api/gost/profile/; JSON body organism=hsapiens, query=[genes], sources=[ids],
user_threshold=<corrected-p cutoff>, significance_threshold_method in {g_SCS,fdr,bonferroni},
domain_scope='custom' + background=[genes] (the custom statistical background), no_evidences=false
(so each term carries its per-query-gene ``intersections`` evidence). Response rows under
``result`` carry name/native/source/p_value(corrected)/term_size/query_size/intersection_size/
significant/intersections.

Live-confirmed 2026-06-12: ``intersections`` is a list aligned to the submitted query order; each
element is itself a list of evidence codes (non-empty = gene annotated to the term, empty = not).

DEGRADE-not-fail: g:Profiler is interpretive, not load-bearing. An outage raises ``GprofilerError``
(Stage 8 catches it and emits a degraded, still-complete result) — contrast STRING (503 fails
the run). On the shared ``with_retry`` + a per-client semaphore, mirroring the other integrations.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from app.integrations.base import with_retry

logger = logging.getLogger("herbaflow.integrations.gprofiler")

_URL = "https://biit.cs.ut.ee/gprofiler/api/gost/profile/"
_ORGANISM = "hsapiens"
_SEM = asyncio.Semaphore(2)


class GprofilerError(Exception):
    """g:Profiler is unavailable — Stage 8 degrades (does NOT fail the run)."""


@dataclass(frozen=True)
class EnrichedTerm:
    source: str
    native: str  # g:Profiler term ID (e.g. "KEGG:04151", "GO:0006955")
    name: str
    p_value: float  # already corrected for multiple testing
    term_size: int
    query_size: int
    intersection_size: int
    intersection: list[str]  # query gene symbols annotated to this term
    significant: bool


class GprofilerClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def profile(
        self,
        *,
        query: list[str],
        background: list[str],
        sources: list[str],
        correction: str,
        user_threshold: float,
    ) -> list[EnrichedTerm]:
        """Run g:GOSt over ``query`` against the custom ``background``. Empty query -> []."""
        genes = [g for g in query if g]
        if not genes:
            return []
        bg = [g for g in background if g]
        body = {
            "organism": _ORGANISM,
            "query": genes,
            "sources": sources,
            "user_threshold": user_threshold,
            "significance_threshold_method": correction,
            "domain_scope": "custom",
            "background": bg,
            "no_evidences": False,
        }

        async def _call() -> httpx.Response:
            async with _SEM:
                resp = await self._client.post(
                    _URL, json=body, headers={"User-Agent": "herbaflow"}, timeout=120.0
                )
            resp.raise_for_status()
            return resp

        try:
            resp = await with_retry(_call)
        except httpx.HTTPError as exc:
            logger.warning("g:Profiler unavailable: %s", exc)
            raise GprofilerError(str(exc)) from exc

        rows = resp.json().get("result", [])
        terms: list[EnrichedTerm] = []
        for row in rows:
            inter = _intersection_genes(genes, row.get("intersections"))
            terms.append(
                EnrichedTerm(
                    source=row.get("source", ""),
                    native=row.get("native", ""),
                    name=row.get("name", ""),
                    p_value=float(row.get("p_value", 1.0)),
                    term_size=int(row.get("term_size", 0)),
                    query_size=int(row.get("query_size", 0)),
                    intersection_size=int(row.get("intersection_size", 0)),
                    intersection=inter,
                    significant=bool(row.get("significant", False)),
                )
            )
        logger.info(
            "g:Profiler: %d term(s) for %d query / %d background genes",
            len(terms),
            len(genes),
            len(bg),
        )
        return terms


def _intersection_genes(query: list[str], intersections: object) -> list[str]:
    """Recover the query gene symbols in a term by zipping query <-> the term's evidence list.

    g:Profiler aligns ``intersections`` to the submitted (mapped) query order; a non-empty
    evidence entry means that query gene is annotated to the term. Defensive: if the shapes
    don't line up, fall back to an empty list (intersection_size is always carried separately).
    """
    if not isinstance(intersections, list):
        return []
    out: list[str] = []
    for gene, evidence in zip(query, intersections, strict=False):
        if evidence:  # non-empty evidence list -> gene is in the term
            out.append(gene)
    return out
