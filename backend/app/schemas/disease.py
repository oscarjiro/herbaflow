from pydantic import BaseModel


class DiseaseResponse(BaseModel):
    disease_id: str
    disease_name: str
    ontology_id: str | None
    ontology_source: str | None
    disease_aliases: list[str] = []
