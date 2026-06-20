"""ORM models and the table registry used by the tz-aware regression test."""

from __future__ import annotations

from app.models.analysis_run import AnalysisRun
from app.models.analysis_run_progress import AnalysisRunProgress
from app.models.base import Base
from app.models.compound import Compound
from app.models.compound_target import CompoundTarget
from app.models.disease import Disease
from app.models.disease_target import DiseaseTarget
from app.models.plant import Plant
from app.models.plant_compound import PlantCompound
from app.models.target import Target

ALL_TABLES = [
    m.__table__
    for m in (
        Disease,
        Plant,
        Compound,
        PlantCompound,
        AnalysisRun,
        AnalysisRunProgress,
        Target,
        CompoundTarget,
        DiseaseTarget,
    )
]

__all__ = [
    "Base",
    "Disease",
    "Plant",
    "Compound",
    "PlantCompound",
    "AnalysisRun",
    "AnalysisRunProgress",
    "Target",
    "CompoundTarget",
    "DiseaseTarget",
    "ALL_TABLES",
]
