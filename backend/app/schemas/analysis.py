"""Analysis run wire DTOs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app import contracts


class Mode(enum.StrEnum):
    auto = "auto"
    guided = "guided"


class AnalysisCreate(BaseModel):
    analysis_name: str | None = None
    plant_ids: list[uuid.UUID] = Field(min_length=1, max_length=contracts.max_plants())
    disease_id: uuid.UUID
    mode: Mode = Mode(contracts.default_mode())
    manual_compound_ids: list[uuid.UUID] = Field(default_factory=list)


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
