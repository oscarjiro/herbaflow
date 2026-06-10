"""PubChem BioAssay client — supplementary measured screens (active outcomes). Degrades to []."""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.integrations.base import with_retry

logger = logging.getLogger("herbaflow.integrations.pubchem_bioassay")

_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_SEM = asyncio.Semaphore(5)


class PubChemBioAssayClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def active_targets_for_inchikey(self, inchikey: str) -> list[str]:
        """Human-candidate UniProt accessions with an Active assay outcome. Degrades to [].

        Parses PubChem's assaysummary column/row table; organism is not present here, so
        human-only is enforced later at UniProt resolution (Stage 3). Keys on column names
        ("Activity Outcome", "Target Accession"), never fixed indices. Never raises.
        """
        url = f"{_BASE}/compound/inchikey/{inchikey}/assaysummary/JSON"

        async def _call() -> httpx.Response:
            async with _SEM:
                resp = await self._client.get(url, timeout=30.0)
            # 404 = no assay data for this compound (handled by the caller as []). Any other
            # error is raised INSIDE so with_retry retries transient 429/5xx before degrading.
            if resp.status_code != 404:
                resp.raise_for_status()
            return resp

        try:
            resp = await with_retry(_call)
            if resp.status_code == 404:
                return []
            table = resp.json().get("Table") or {}
        except httpx.HTTPError as exc:
            logger.warning("PubChem BioAssay degraded for %s: %s", inchikey, exc)
            return []
        except ValueError as exc:  # malformed JSON
            logger.warning("PubChem BioAssay parse error for %s: %s", inchikey, exc)
            return []

        columns: list[str] = ((table.get("Columns") or {}).get("Column")) or []
        try:
            outcome_idx = columns.index("Activity Outcome")
            acc_idx = columns.index("Target Accession")
        except ValueError:
            logger.warning("PubChem BioAssay: unexpected columns for %s", inchikey)
            return []

        accs: list[str] = []
        for row in table.get("Row") or []:
            cells = row.get("Cell") or []
            if len(cells) <= max(outcome_idx, acc_idx):
                continue
            if (cells[outcome_idx] or "").strip().lower() != "active":
                continue
            acc = (cells[acc_idx] or "").strip().upper()
            if acc and acc not in accs:
                accs.append(acc)
        logger.info("PubChem BioAssay %s: %d active target(s)", inchikey, len(accs))
        return accs
