import inspect

import app.models as models
from sqlmodel import SQLModel

from analysis.stages import stage7_hub_genes


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
