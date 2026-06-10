"""UniProt REST client — human (9606) accession + gene-symbol resolution."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from app.integrations.base import with_retry

logger = logging.getLogger("herbaflow.integrations.uniprot")

_BASE = "https://rest.uniprot.org/uniprotkb/search"
_FIELDS = "accession,gene_primary,protein_name"
_SEM = asyncio.Semaphore(10)


@dataclass(frozen=True)
class UniProtRecord:
    uniprot_accession: str
    gene_symbol: str | None
    protein_name: str | None


class UniProtClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def resolve(self, accession: str) -> UniProtRecord | None:
        """Resolve an accession to its human (organism_id:9606) record, or None."""
        acc = accession.strip().upper()
        return await self._top_human(f"accession:{acc} AND organism_id:9606", label=acc)

    async def resolve_symbol(self, symbol: str) -> UniProtRecord | None:
        """Resolve a gene symbol to its top human (organism_id:9606) record, or None."""
        sym = symbol.strip().upper()
        return await self._top_human(f"gene_exact:{sym} AND organism_id:9606", label=sym)

    async def _top_human(self, query: str, *, label: str) -> UniProtRecord | None:
        params = {"query": query, "fields": _FIELDS, "format": "json", "size": "1"}
        logger.info("UniProt resolve: %s (9606)", label)

        async def _call() -> httpx.Response:
            async with _SEM:
                resp = await self._client.get(_BASE, params=params, timeout=30.0)
            resp.raise_for_status()  # raise INSIDE so with_retry retries transient 429/5xx
            return resp

        try:
            resp = await with_retry(_call)
        except httpx.HTTPStatusError as exc:
            # A 400 means the value is not a resolvable UniProt query — e.g. a ChEMBL target
            # whose accession is a non-UniProt id (GenBank etc.). Treat as "no human record"
            # and skip, rather than failing the whole run. 5xx (a real outage) still raises.
            if exc.response.status_code == 400:
                logger.info("UniProt: unresolvable accession %s (400) — skipping", label)
                return None
            raise

        results = resp.json().get("results", [])
        if not results:
            logger.info("UniProt: no human record for %s", label)
            return None
        r = results[0]
        genes = r.get("genes") or []
        gene = (genes[0].get("geneName", {}) or {}).get("value") if genes else None
        prot = (
            (r.get("proteinDescription", {}) or {})
            .get("recommendedName", {})
            .get("fullName", {})
            .get("value")
        )
        return UniProtRecord(
            uniprot_accession=r.get("primaryAccession", label),
            gene_symbol=gene,
            protein_name=prot,
        )
