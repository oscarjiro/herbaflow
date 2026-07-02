from app.models import AnalysisRun, Compound, Disease, Plant, Target


def test_dropped_orm_attributes_absent():
    for attr in ("canonical_key", "qed_score", "source_id"):
        assert attr not in Compound.__table__.columns
    assert "idempotency_key" not in AnalysisRun.__table__.columns
    for m in (Plant, Target, Disease):
        assert "canonical_key" not in m.__table__.columns
        assert "source_id" not in m.__table__.columns


def test_added_and_fixed():
    assert "cas_id" in Compound.__table__.columns
    assert AnalysisRun.__table__.columns["mode"].server_default.arg.text == "'guided'"


def test_alias_and_source_models_removed():
    import app.models as models

    for gone in ("SourceSystem", "PlantAlias", "DiseaseAlias"):
        assert not hasattr(models, gone), gone
