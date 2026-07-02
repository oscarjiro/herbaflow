from app.schemas.compound import ResolvedCompound
from app.schemas.disease import DiseaseRead
from app.schemas.plant import PlantRead
from app.schemas.target import ResolvedTarget


def test_canonical_key_not_in_response_schemas():
    for m in (ResolvedCompound, ResolvedTarget, PlantRead, DiseaseRead):
        assert "canonical_key" not in m.model_fields, m.__name__
