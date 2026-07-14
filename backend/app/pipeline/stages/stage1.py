"""Stage 1 — compound selection from selected plants (DB-only)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compound import Compound
from app.models.plant_compound import PlantCompound

logger = logging.getLogger("herbaflow.pipeline")

# Maps the DB ``compounds.source_name`` (which upstream database anchored the compound's canonical
# structure) to the contract data-source display name in
# ``shared/contracts/analysis.json`` → stage_sources.computed["1"]. Stage 1 emits the distinct
# contributing display names for the run; the FE filters the static source list to these, so a
# source that anchored 0 compounds this run (e.g. ChEMBL) never appears. Rows with no / unmapped
# source_name (name-only ETL rows) contribute nothing.
_SOURCE_DISPLAY_NAME = {
    "KNApSAcK World": "KNApSAcK",
    "PubChem": "PubChem",
}


@dataclass(frozen=True)
class CompoundRow:
    plant_id: uuid.UUID
    compound_id: uuid.UUID
    canonical_name: str | None
    smiles: str | None = None
    inchikey: str | None = None
    pubchem_cid: str | None = None
    source_url: str | None = None
    source_name: str | None = None


def select_compounds(rows: list[CompoundRow]) -> dict[str, Any]:
    """Dedupe compounds across the selected plants, keeping per-plant attribution."""
    compounds: dict[str, dict[str, Any]] = {}
    per_plant: dict[str, list[str]] = {}
    contributing: list[str] = []
    for row in rows:
        cid = str(row.compound_id)
        compounds.setdefault(
            cid,
            {
                "compound_id": cid,
                "canonical_name": row.canonical_name,
                "smiles": row.smiles,
                "inchikey": row.inchikey,
                "pubchem_cid": row.pubchem_cid,
                "source_url": row.source_url,
            },
        )
        display = _SOURCE_DISPLAY_NAME.get((row.source_name or "").strip())
        if display is not None and display not in contributing:
            contributing.append(display)
        per_plant.setdefault(str(row.plant_id), [])
        if cid not in per_plant[str(row.plant_id)]:
            per_plant[str(row.plant_id)].append(cid)
    return {
        "compounds": list(compounds.values()),
        "per_plant": per_plant,
        "count": len(compounds),
        "contributing_sources": contributing,
        "state": "computed",
    }


async def run(session: AsyncSession, plant_ids: list[uuid.UUID]) -> dict[str, Any]:
    """Fetch plant-compound links for the selected plants and select compounds."""
    stmt = (
        select(
            PlantCompound.plant_id,
            PlantCompound.compound_id,
            Compound.canonical_name,
            Compound.smiles,
            Compound.inchi_key,
            Compound.pubchem_cid,
            Compound.source_url,
            Compound.source_name,
        )
        .join(Compound, Compound.compound_id == PlantCompound.compound_id)
        .where(PlantCompound.plant_id.in_(plant_ids))
    )
    result = await session.execute(stmt)
    rows = [
        CompoundRow(
            plant_id=r.plant_id,
            compound_id=r.compound_id,
            canonical_name=r.canonical_name,
            smiles=r.smiles,
            inchikey=r.inchi_key,
            pubchem_cid=r.pubchem_cid,
            source_url=r.source_url,
            source_name=r.source_name,
        )
        for r in result.all()
    ]
    out = select_compounds(rows)
    logger.info("stage 1: %d plant-link row(s) -> %d distinct compound(s)", len(rows), out["count"])
    return out
