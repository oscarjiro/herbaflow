# backend/tests/unit/test_models_s6.py
import app.models as models


def test_import_batch_model_removed():
    assert not hasattr(models, "ImportBatch")
    assert "ImportBatch" not in models.__all__
