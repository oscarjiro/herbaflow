"""ORM models and the table registry used by the tz-aware regression test."""

from __future__ import annotations

from app.models.analysis_run import AnalysisRun
from app.models.base import Base
from app.models.compound import Compound
from app.models.disease import Disease
from app.models.plant import Plant
from app.models.plant_compound import PlantCompound

ALL_TABLES = [m.__table__ for m in (Disease, Plant, Compound, PlantCompound, AnalysisRun)]

__all__ = [
    "Base",
    "Disease",
    "Plant",
    "Compound",
    "PlantCompound",
    "AnalysisRun",
    "ALL_TABLES",
]
