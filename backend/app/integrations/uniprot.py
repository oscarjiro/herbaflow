"""UniProt REST client — human (9606) accession + gene-symbol resolution."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum

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


class UniProtReason(StrEnum):
    """Why a resolution produced no record — two distinct, honestly-reportable causes."""

    INVALID_ID = "invalid_id"  # HTTP 400 — not a resolvable UniProt query
    NO_HUMAN_RECORD = "no_human_record"  # valid query, zero 9606 results


@dataclass(frozen=True)
class UniProtResolution:
    """Result of a UniProt lookup: the record, or the reason it could not be resolved."""

    record: UniProtRecord | None
    reason: UniProtReason | None  # set iff record is None


class UniProtClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def resolve(self, accession: str) -> UniProtResolution:
        """Resolve an accession (primary OR secondary) to its human (9606) record.

        ``accession:`` matches only the primary accession; ``sec_acc:`` matches secondary
        (merged/retired) accessions. Searching both means any alias of an entry resolves to
        the same record (whose ``primaryAccession`` is returned), so callers can canonicalize
        identity on the primary. See https://www.uniprot.org/help/query-fields.

        On a miss the ``reason`` distinguishes a 400 (``INVALID_ID`` — not a resolvable
        UniProt query) from a valid query with zero human hits (``NO_HUMAN_RECORD``).
        """
        acc = accession.strip().upper()
        return await self._top_human(
            f"(accession:{acc} OR sec_acc:{acc}) AND organism_id:9606", label=acc
        )

    async def resolve_symbol(self, symbol: str) -> UniProtResolution:
        """Resolve a gene symbol to its top human (9606) record, preferring reviewed (Swiss-Prot).

        UniProt search returns ``size=1`` with no inherent reviewed-first ordering, so a gene's
        top hit can be an unreviewed TrEMBL entry (e.g. EGFR -> A2VCQ7 instead of reviewed
        P00533). Query reviewed entries first; only on a genuine no-human miss fall back to the
        unreviewed pool, so a gene with a TrEMBL-only human record still resolves.
        ``reviewed:true`` is the documented UniProtKB query field
        (https://www.uniprot.org/help/query-fields).
        """
        sym = symbol.strip().upper()
        reviewed = await self._top_human(
            f"gene_exact:{sym} AND organism_id:9606 AND reviewed:true", label=sym
        )
        # Only fall back when reviewed genuinely had no human record. A 400 (INVALID_ID) is
        # surfaced, not silently retried.
        if reviewed.record is not None or reviewed.reason is not UniProtReason.NO_HUMAN_RECORD:
            return reviewed
        return await self._top_human(f"gene_exact:{sym} AND organism_id:9606", label=sym)

    async def _top_human(self, query: str, *, label: str) -> UniProtResolution:
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
            # whose accession is a non-UniProt id (GenBank etc.). Treat as INVALID_ID and skip,
            # rather than failing the whole run. 5xx (a real outage) still raises.
            if exc.response.status_code == 400:
                logger.info("UniProt: unresolvable accession %s (400) — skipping", label)
                return UniProtResolution(None, UniProtReason.INVALID_ID)
            raise

        results = resp.json().get("results", [])
        if not results:
            logger.info("UniProt: no human record for %s", label)
            return UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)
        r = results[0]
        genes = r.get("genes") or []
        gene = (genes[0].get("geneName", {}) or {}).get("value") if genes else None
        prot = (
            (r.get("proteinDescription", {}) or {})
            .get("recommendedName", {})
            .get("fullName", {})
            .get("value")
        )
        return UniProtResolution(
            record=UniProtRecord(
                uniprot_accession=r.get("primaryAccession", label),
                gene_symbol=gene,
                protein_name=prot,
            ),
            reason=None,
        )
