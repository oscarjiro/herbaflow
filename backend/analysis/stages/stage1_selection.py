from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories.compound_repo import get_compounds_for_plants


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    params = run.parameters or {}
    plant_ids = params.get("_plant_ids", [])

    if not plant_ids:
        return {"compound_ids": [], "compound_count": 0, "error": "No plant IDs provided"}

    compounds = await get_compounds_for_plants(session, plant_ids)
    return {
        "compound_count": len(compounds),
        "compound_ids": [c.compound_id for c in compounds],
        "plant_ids": plant_ids,
    }
