"""PubChem PUG-REST client — compound enrichment by InChIKey. Verified 2025 field names."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.integrations.base import with_retry

logger = logging.getLogger("herbaflow.integrations.pubchem")

_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
# 2025 rename: CanonicalSMILES->ConnectivitySMILES (no stereo), IsomericSMILES->SMILES (stereo).
# Request both new names + the legacy CanonicalSMILES as a fallback; prefer stereo `SMILES`.
_PROPS = "MolecularFormula,MolecularWeight,SMILES,ConnectivitySMILES,IUPACName,CanonicalSMILES"


@dataclass(frozen=True)
class PubChemRecord:
    pubchem_cid: str | None
    smiles: str | None
    molecular_formula: str | None
    molecular_weight: float | None
    name: str | None


class PubChemClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def fetch_by_inchikey(self, inchikey: str) -> PubChemRecord | None:
        logger.info("PubChem lookup: %s", inchikey)
        url = f"{_BASE}/compound/inchikey/{inchikey}/property/{_PROPS}/JSON"

        async def _call() -> httpx.Response:
            return await self._client.get(url, timeout=20.0)

        resp = await with_retry(_call)
        if resp.status_code == 404:
            logger.info("PubChem: no record for %s", inchikey)
            return None
        resp.raise_for_status()
        props = resp.json().get("PropertyTable", {}).get("Properties", [])
        if not props:
            return None
        p = props[0]
        mw = p.get("MolecularWeight")
        return PubChemRecord(
            pubchem_cid=str(p["CID"]) if p.get("CID") is not None else None,
            smiles=p.get("SMILES") or p.get("ConnectivitySMILES") or p.get("CanonicalSMILES"),
            molecular_formula=p.get("MolecularFormula"),
            molecular_weight=float(mw) if mw not in (None, "") else None,
            name=p.get("IUPACName"),
        )
