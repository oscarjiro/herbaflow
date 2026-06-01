import inspect

import app.models as models
from sqlmodel import SQLModel

from analysis.stages import stage7_hub_genes
from app.models.compound import PlantCompound
from app.models.target import CompoundTarget


def test_stage7_run_has_no_target_rankings_write():
    src = inspect.getsource(stage7_hub_genes.run)
    assert "TargetRanking" not in src, "stage7 must not write the target_rankings table"
    assert "session.add" not in src, "stage7 must not persist rows"
    assert "session.commit" not in src


def test_dead_model_classes_removed():
    exported = set(getattr(models, "__all__", []))
    for name in ("TargetRanking", "Pathway", "TargetPathway", "PpiEdge"):
        assert not hasattr(models, name), f"{name} should be deleted"
        assert name not in exported, f"{name} should not be exported"


def test_dead_tables_absent_from_metadata():
    tables = set(SQLModel.metadata.tables)
    for t in ("target_rankings", "pathways", "target_pathways", "ppi_edges"):
        assert t not in tables, f"{t} must not be mapped"


def test_evidence_type_removed():
    assert "evidence_type" not in PlantCompound.model_fields
    assert "evidence_type" not in CompoundTarget.model_fields
    assert "prediction_method" in CompoundTarget.model_fields  # kept


from app.models.plant import Plant
from app.models.disease import Disease
from app.models.compound import Compound
from app.models.target import Target, DiseaseTarget


def test_confidence_removed_everywhere():
    for m in (Plant, Disease, Compound, PlantCompound, Target, CompoundTarget, DiseaseTarget):
        assert "confidence" not in m.model_fields, f"{m.__name__}.confidence must be dropped"
    # meaningful score columns survive
    assert "score" in CompoundTarget.model_fields
    assert "score" in DiseaseTarget.model_fields
    assert "association_type" in DiseaseTarget.model_fields


def test_source_raw_ids_removed():
    assert "source_plant_raw_id" not in PlantCompound.model_fields
    assert "source_compound_raw_id" not in PlantCompound.model_fields
