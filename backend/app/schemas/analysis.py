"""Analysis run wire DTOs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app import contracts


class Mode(enum.StrEnum):
    auto = "auto"
    guided = "guided"


class PlantInputMode(enum.StrEnum):
    selection = "selection"
    manual_compounds = "manual_compounds"
    manual_targets = "manual_targets"


class DiseaseInputMode(enum.StrEnum):
    selection = "selection"
    manual_disease_targets = "manual_disease_targets"


class AnalysisCreate(BaseModel):
    analysis_name: str | None = None
    plant_input_mode: PlantInputMode = PlantInputMode(contracts.default_plant_input_mode())
    disease_input_mode: DiseaseInputMode = DiseaseInputMode(contracts.default_disease_input_mode())
    plant_ids: list[uuid.UUID] = Field(default_factory=list, max_length=contracts.max_plants())
    disease_id: uuid.UUID | None = None
    mode: Mode = Mode(contracts.default_mode())
    manual_compound_ids: list[uuid.UUID] = Field(default_factory=list)
    manual_target_ids: list[uuid.UUID] = Field(default_factory=list)
    manual_disease_target_ids: list[uuid.UUID] = Field(default_factory=list)
    plant_label: str | None = Field(default=None, max_length=200)
    disease_label: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _validate_modes(self) -> AnalysisCreate:
        p, d = self.plant_input_mode, self.disease_input_mode
        # Plant side: required + forbidden inputs per mode.
        if p is PlantInputMode.selection:
            if not self.plant_ids:
                raise ValueError("selection mode requires at least one plant_ids.")
            if self.plant_label is not None:
                raise ValueError("plant_label is only allowed in a manual plant mode.")
        elif p is PlantInputMode.manual_compounds:
            if self.plant_ids:
                raise ValueError("manual_compounds mode forbids plant_ids.")
            if not self.manual_compound_ids:
                raise ValueError("manual_compounds mode requires manual_compound_ids.")
            if self.manual_target_ids:
                raise ValueError("manual_compounds mode forbids manual_target_ids.")
        else:  # manual_targets
            if self.plant_ids or self.manual_compound_ids:
                raise ValueError("manual_targets mode forbids plant_ids and manual_compound_ids.")
            if not self.manual_target_ids:
                raise ValueError("manual_targets mode requires manual_target_ids.")
        # Disease side.
        if d is DiseaseInputMode.selection:
            if self.disease_id is None:
                raise ValueError("selection disease mode requires disease_id.")
            if self.disease_label is not None:
                raise ValueError("disease_label is only allowed in manual_disease_targets mode.")
            if self.manual_disease_target_ids:
                raise ValueError("selection disease mode forbids manual_disease_target_ids.")
        else:  # manual_disease_targets
            if self.disease_id is not None:
                raise ValueError("manual_disease_targets mode forbids disease_id.")
            if not self.manual_disease_target_ids:
                raise ValueError("manual_disease_targets mode requires manual_disease_target_ids.")
        return self


class ResetFromRequest(BaseModel):
    """Body for POST /analyses/{id}/reset-from/{stage}.

    ``parameters`` is a stage-keyed map of ADME param overrides, e.g.
    ``{"2": {"max_violations": 0}}``.  Only the entry matching the target
    stage is extracted and forwarded to the service.
    """

    parameters: dict[str, dict[str, Any]] | None = None


class StageEditRequest(BaseModel):
    """Body for POST /analyses/{id}/stages/{stage}/edit."""

    add: list[uuid.UUID] = Field(default_factory=list)
    remove: list[uuid.UUID] = Field(default_factory=list)


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_id: uuid.UUID
    analysis_name: str | None
    disease_id: uuid.UUID | None
    mode: Mode
    status: str | None
    current_stage: int | None
    parameters: dict[str, Any] = Field(default_factory=dict)
    stage_results: dict[str, Any]
    created_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None
    error_message: str | None
