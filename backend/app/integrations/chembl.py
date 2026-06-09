"""ChEMBL client — measured compound→target bioactivities (human, single-protein).

The ChEMBL ``/activity`` endpoint does NOT carry the target-confidence score or the
UniProt accession, so a single-resource read is impossible. This client performs the
correct multi-resource join:

  1. ``/activity`` — paginated by InChIKey; yields pchembl, standard_type, organism,
     ``target_chembl_id`` and ``assay_chembl_id`` (cheap pre-filters applied here).
  2. ``/assay`` — batch-resolves ``assay_chembl_id -> confidence_score``.
  3. ``/target`` — batch-resolves ``target_chembl_id -> target_components[0].accession``
     for human SINGLE PROTEIN targets.

The three resources are then joined, keeping the strongest pchembl per accession.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.errors import ServiceUnavailableError
from app.integrations.base import with_retry

logger = logging.getLogger("herbaflow.integrations.chembl")

_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_PAGE = 1000
_CHUNK = 50
_ACTIVITY_TYPES = {"IC50", "Ki", "Kd", "EC50"}
_HUMAN_NAME = "Homo sapiens"
_HUMAN_TAX = 9606
_SINGLE_PROTEIN = "SINGLE PROTEIN"
_SEM = asyncio.Semaphore(10)


@dataclass(frozen=True)
class ChemblHit:
    uniprot_accession: str
    pchembl_value: float
    activity_type: str


def _chunked(items: list[str], size: int = _CHUNK) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class ChemblClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def targets_for_inchikey(
        self, inchikey: str, *, min_pchembl: float, min_confidence: int
    ) -> list[ChemblHit]:
        """All measured single-protein human targets for a compound, filtered.

        Joins ``/activity`` (pchembl, type), ``/assay`` (confidence) and ``/target``
        (UniProt accession). Raises ServiceUnavailableError on outage (load-bearing).
        """
        try:
            candidates = await self._candidate_activities(inchikey, min_pchembl=min_pchembl)
            confidence = await self._assay_confidence(sorted({c[1] for c in candidates}))
            kept = [c for c in candidates if confidence.get(c[1], -1) >= min_confidence]
            accessions = await self._target_accessions(sorted({c[0] for c in kept}))
        except httpx.HTTPError as exc:
            logger.warning("ChEMBL outage for %s: %s", inchikey, exc)
            raise ServiceUnavailableError(detail="ChEMBL is unavailable.") from exc

        hits: dict[str, ChemblHit] = {}
        for target_id, _assay_id, pchembl, std_type in kept:
            acc = accessions.get(target_id)
            if not acc:
                continue
            cur = hits.get(acc)
            if cur is None or pchembl > cur.pchembl_value:
                hits[acc] = ChemblHit(acc, pchembl, std_type)
        logger.info("ChEMBL %s: %d measured human target(s)", inchikey, len(hits))
        return list(hits.values())

    async def _candidate_activities(
        self, inchikey: str, *, min_pchembl: float
    ) -> list[tuple[str, str, float, str]]:
        """Paginate /activity; return (target_id, assay_id, pchembl, std_type) candidates."""
        candidates: list[tuple[str, str, float, str]] = []
        offset = 0
        while True:
            body = await self._get_json(
                "/activity",
                {
                    "molecule_structures__standard_inchi_key": inchikey,
                    "limit": str(_PAGE),
                    "offset": str(offset),
                    "format": "json",
                },
            )
            page = body.get("activities") or []
            for row in page:
                cand = self._candidate(row, min_pchembl=min_pchembl)
                if cand is not None:
                    candidates.append(cand)
            nxt = (body.get("page_meta") or {}).get("next")
            if not nxt or not page:
                break
            offset += _PAGE
        return candidates

    @staticmethod
    def _candidate(
        row: dict[str, Any], *, min_pchembl: float
    ) -> tuple[str, str, float, str] | None:
        pchembl = row.get("pchembl_value")
        if pchembl is None:
            return None
        try:
            pval = float(pchembl)
        except (TypeError, ValueError):
            return None
        if pval < min_pchembl:
            return None
        std_type = row.get("standard_type") or ""
        if std_type not in _ACTIVITY_TYPES:
            return None
        if (
            row.get("target_tax_id") != _HUMAN_TAX
            and (row.get("target_organism") or "") != _HUMAN_NAME
        ):
            return None
        target_id = row.get("target_chembl_id") or ""
        assay_id = row.get("assay_chembl_id") or ""
        if not target_id or not assay_id:
            return None
        return (target_id, assay_id, pval, std_type)

    async def _assay_confidence(self, assay_ids: list[str]) -> dict[str, int]:
        """Batch-resolve assay_chembl_id -> confidence_score across /assay (chunked)."""
        confidence: dict[str, int] = {}
        for chunk in _chunked(assay_ids):
            async for assay in self._paginate(
                "/assay",
                "assays",
                {"assay_chembl_id__in": ",".join(chunk)},
            ):
                aid = assay.get("assay_chembl_id")
                score = assay.get("confidence_score")
                if aid and score is not None:
                    confidence[aid] = int(score)
        return confidence

    async def _target_accessions(self, target_ids: list[str]) -> dict[str, str]:
        """Batch-resolve target_chembl_id -> accession for human SINGLE PROTEINs (chunked)."""
        accessions: dict[str, str] = {}
        for chunk in _chunked(target_ids):
            async for target in self._paginate(
                "/target",
                "targets",
                {"target_chembl_id__in": ",".join(chunk)},
            ):
                tid = target.get("target_chembl_id")
                if not tid:
                    continue
                if target.get("target_type") != _SINGLE_PROTEIN:
                    continue
                if target.get("tax_id") != _HUMAN_TAX:
                    continue
                comps = target.get("target_components") or []
                acc = comps[0].get("accession") if comps else None
                if acc:
                    accessions[tid] = acc
        return accessions

    async def _paginate(self, path: str, key: str, params: dict[str, str]) -> Any:
        """Yield each item under ``key``, following ``page_meta.next`` via offset."""
        offset = 0
        while True:
            page_params = dict(params)
            page_params.update({"limit": str(_PAGE), "offset": str(offset), "format": "json"})
            body = await self._get_json(path, page_params)
            page = body.get(key) or []
            for item in page:
                yield item
            nxt = (body.get("page_meta") or {}).get("next")
            if not nxt or not page:
                break
            offset += _PAGE

    async def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{_BASE}{path}"

        async def _call(url: str = url, params: dict[str, str] = params) -> httpx.Response:
            async with _SEM:
                resp = await self._client.get(url, params=params, timeout=30.0)
            resp.raise_for_status()  # raise INSIDE so with_retry retries transient 5xx
            return resp

        resp = await with_retry(_call)
        body: dict[str, Any] = resp.json()
        return body
