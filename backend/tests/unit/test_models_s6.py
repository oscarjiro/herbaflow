# backend/tests/unit/test_models_s6.py
import app.models as models


def test_import_batch_model_removed():
    assert not hasattr(models, "ImportBatch")
    assert "ImportBatch" not in models.__all__


from app.models import (
    AnalysisRun,
    Compound,
    CompoundAlias,
    CompoundTarget,
    Disease,
    DiseaseAlias,
    DiseaseTarget,
    Plant,
    PlantAlias,
    PlantCompound,
    Target,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID


def test_no_source_batch_id_on_models():
    for model in (Plant, PlantAlias, Compound, CompoundAlias, Disease, Target):
        assert "source_batch_id" not in model.__table__.c, model.__name__


_ID_COLUMNS = {
    Plant: ["plant_id"],
    PlantAlias: ["alias_id", "plant_id"],
    Compound: ["compound_id"],
    CompoundAlias: ["compound_alias_id", "compound_id"],
    PlantCompound: ["plant_compound_id", "plant_id", "compound_id"],
    Disease: ["disease_id"],
    DiseaseAlias: ["disease_alias_id", "disease_id"],
    Target: ["target_id"],
    CompoundTarget: ["compound_target_id", "compound_id", "target_id"],
    DiseaseTarget: ["disease_target_id", "disease_id", "target_id"],
    AnalysisRun: ["disease_id"],
}


def test_entity_ids_are_uuid_columns():
    for model, cols in _ID_COLUMNS.items():
        for name in cols:
            coltype = model.__table__.c[name].type
            assert isinstance(coltype, PGUUID), f"{model.__name__}.{name}"
            assert coltype.as_uuid is False, f"{model.__name__}.{name}"
