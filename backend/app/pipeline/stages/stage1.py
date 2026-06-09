"""Stage 1 — compound selection from selected plants (DB-only)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compound import Compound
from app.models.plant_compound import PlantCompound
from app.repositories.compound import CompoundRepository


@dataclass(frozen=True)
class CompoundRow:
    plant_id: uuid.UUID
    compound_id: uuid.UUID
    canonical_name: str | None


def select_compounds(
    rows: list[CompoundRow], manual: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Dedupe compounds across plants, keep per-plant attribution."""
    compounds: dict[str, dict[str, Any]] = {}
    per_plant: dict[str, list[str]] = {}
    for row in rows:
        cid = str(row.compound_id)
        compounds.setdefault(cid, {"compound_id": cid, "canonical_name": row.canonical_name})
        per_plant.setdefault(str(row.plant_id), [])
        if cid not in per_plant[str(row.plant_id)]:
            per_plant[str(row.plant_id)].append(cid)
    for m in manual or []:
        cid = str(m["compound_id"])
        compounds.setdefault(cid, {"compound_id": cid, "canonical_name": m.get("canonical_name")})
        per_plant.setdefault("manual", [])
        if cid not in per_plant["manual"]:
            per_plant["manual"].append(cid)
    return {
        "compounds": list(compounds.values()),
        "per_plant": per_plant,
        "count": len(compounds),
        "state": "computed",
    }


async def run(
    session: AsyncSession,
    plant_ids: list[uuid.UUID],
    manual_compound_ids: list[uuid.UUID] | None = None,
) -> dict[str, Any]:
    """Fetch plant-compound links for the selected plants and select compounds."""
    stmt = (
        select(
            PlantCompound.plant_id,
            PlantCompound.compound_id,
            Compound.canonical_name,
        )
        .join(Compound, Compound.compound_id == PlantCompound.compound_id)
        .where(PlantCompound.plant_id.in_(plant_ids))
    )
    result = await session.execute(stmt)
    rows = [
        CompoundRow(plant_id=r.plant_id, compound_id=r.compound_id, canonical_name=r.canonical_name)
        for r in result.all()
    ]
    manual: list[dict[str, Any]] = []
    if manual_compound_ids:
        for comp in await CompoundRepository(session).get_many(manual_compound_ids):
            manual.append(
                {"compound_id": str(comp.compound_id), "canonical_name": comp.canonical_name}
            )
    return select_compounds(rows, manual=manual)
