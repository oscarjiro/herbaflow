from pydantic import BaseModel


class PlantResponse(BaseModel):
    plant_id: str
    canonical_scientific_name: str
    family_name: str | None
    compound_count: int = 0
