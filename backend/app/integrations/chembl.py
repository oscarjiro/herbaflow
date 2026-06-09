"""ChEMBL client — measured compound→target bioactivities (human, single-protein)."""

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
_ACTIVITY_TYPES = {"IC50", "Ki", "Kd", "EC50"}
_HUMAN = "Homo sapiens"
_SEM = asyncio.Semaphore(10)


@dataclass(frozen=True)
class ChemblHit:
    uniprot_accession: str
    pchembl_value: float
    activity_type: str


class ChemblClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def targets_for_inchikey(
        self, inchikey: str, *, min_pchembl: float, min_confidence: int
    ) -> list[ChemblHit]:
        """All measured single-protein human targets for a compound, filtered. Paginated.

        Raises ServiceUnavailableError on outage (load-bearing source).
        """
        try:
            rows = await self._all_activities(inchikey)
        except httpx.HTTPError as exc:
            logger.warning("ChEMBL outage for %s: %s", inchikey, exc)
            raise ServiceUnavailableError(detail="ChEMBL is unavailable.") from exc

        hits: dict[str, ChemblHit] = {}
        for r in rows:
            pchembl = r.get("pchembl_value")
            conf = r.get("target_confidence_score")
            if pchembl is None or conf is None:
                continue
            std_type = r.get("standard_type") or ""
            if std_type not in _ACTIVITY_TYPES:
                continue
            if (r.get("target_organism") or "") != _HUMAN:
                continue
            if float(pchembl) < min_pchembl or int(conf) < min_confidence:
                continue
            comps = r.get("target_components") or []
            acc = comps[0].get("accession") if comps else None
            if not acc:
                continue
            val = float(pchembl)
            cur = hits.get(acc)
            if cur is None or val > cur.pchembl_value:
                hits[acc] = ChemblHit(acc, val, std_type)
        logger.info("ChEMBL %s: %d measured human target(s)", inchikey, len(hits))
        return list(hits.values())

    async def _all_activities(self, inchikey: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            params = {
                "molecule_chembl_id__isnull": "false",
                "molecule_structures__standard_inchi_key": inchikey,
                "target_type": "SINGLE PROTEIN",
                "limit": str(_PAGE),
                "offset": str(offset),
                "format": "json",
            }

            async def _call(params: dict[str, str] = params) -> httpx.Response:
                async with _SEM:
                    resp = await self._client.get(f"{_BASE}/activity", params=params, timeout=30.0)
                resp.raise_for_status()  # raise INSIDE so with_retry retries transient 5xx
                return resp

            resp = await with_retry(_call)
            body = resp.json()
            page = body.get("activities", [])
            rows.extend(page)
            nxt = (body.get("page_meta") or {}).get("next")
            if not nxt or not page:
                break
            offset += _PAGE
        return rows
