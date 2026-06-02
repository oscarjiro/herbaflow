# backend/app/models/__init__.py
from .plant import Plant, PlantAlias
from .compound import Compound, CompoundAlias, PlantCompound
from .disease import Disease, DiseaseAlias
from .target import Target, CompoundTarget, DiseaseTarget
from .analysis import AnalysisRun

__all__ = [
    "Plant", "PlantAlias",
    "Compound", "CompoundAlias", "PlantCompound",
    "Disease", "DiseaseAlias",
    "Target", "CompoundTarget", "DiseaseTarget",
    "AnalysisRun",
]
