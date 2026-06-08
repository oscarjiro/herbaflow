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
    mode: Mode = Mode.auto


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_id: uuid.UUID
    analysis_name: str | None
    disease_id: uuid.UUID | None
    mode: Mode
    status: str | None
    current_stage: int | None
    stage_results: dict[str, Any]
    created_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None
    error_message: str | None
