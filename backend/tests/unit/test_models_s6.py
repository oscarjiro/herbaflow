# backend/tests/unit/test_models_s6.py
import app.models as models


def test_import_batch_model_removed():
    assert not hasattr(models, "ImportBatch")
    assert "ImportBatch" not in models.__all__


from app.models import Plant, PlantAlias, Compound, CompoundAlias, Disease, Target


def test_no_source_batch_id_on_models():
    for model in (Plant, PlantAlias, Compound, CompoundAlias, Disease, Target):
        assert "source_batch_id" not in model.__table__.c, model.__name__
