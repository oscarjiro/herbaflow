from app.models import PlantCompound
from app.models.analysis import AnalysisRun
from app.repositories.compound_repo import get_compounds_for_plants
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analysis.models import PipelineConfig


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    params = run.parameters or {}
    plant_ids = params.get("_plant_ids", [])

    if not plant_ids:
        return {
            "compound_ids": [],
            "compound_count": 0,
            "total_compounds": 0,
            "plants_covered": 0,
            "plant_ids": [],
            "compounds": [],
            "error": "No plant IDs provided",
        }

    compounds = await get_compounds_for_plants(session, plant_ids)
    compound_ids = [str(c.compound_id) for c in compounds]

    # Build compound → plant_ids mapping from PlantCompound junction
    stmt = select(PlantCompound).where(
        PlantCompound.plant_id.in_(plant_ids),
        PlantCompound.compound_id.in_(compound_ids),
    )
    result = await session.execute(stmt)
    pc_rows = result.scalars().all()
    compound_to_plants: dict[str, list[str]] = {}
    for pc in pc_rows:
        compound_to_plants.setdefault(pc.compound_id, []).append(pc.plant_id)

    enriched = [
        {
            "compound_id": str(c.compound_id),
            "canonical_name": c.canonical_name or str(c.compound_id),
            "plant_ids": compound_to_plants.get(str(c.compound_id), plant_ids),
        }
        for c in compounds
    ]

    return {
        # Pipeline chain compatibility (stage2 reads compound_ids)
        "compound_ids": compound_ids,
        "compound_count": len(compounds),
        "plant_ids": plant_ids,
        # Frontend display fields
        "total_compounds": len(compounds),
        "plants_covered": len(set(plant_ids)),
        "compounds": enriched,
    }
