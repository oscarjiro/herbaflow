# backend/app/models/__init__.py
from .analysis import AnalysisRun
from .compound import Compound, CompoundAlias, PlantCompound
from .disease import Disease, DiseaseAlias
from .plant import Plant, PlantAlias
from .target import CompoundTarget, DiseaseTarget, Target

__all__ = [
    "Plant", "PlantAlias",
    "Compound", "CompoundAlias", "PlantCompound",
    "Disease", "DiseaseAlias",
    "Target", "CompoundTarget", "DiseaseTarget",
    "AnalysisRun",
]
