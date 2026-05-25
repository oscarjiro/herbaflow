from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Any


class CreateAnalysisRequest(BaseModel):
    name: str
    mode: str = "guided"
    plant_ids: list[str] = []
    disease_ids: list[str]
    parameters: dict[str, Any] = {}


class AnalysisStatusResponse(BaseModel):
    analysis_id: UUID
    status: str
    mode: str
    current_stage: int | None
    progress: dict[str, int]
    created_at: datetime | None
    updated_at: datetime | None
    error_message: str | None = None
    expires_at: datetime | None = None


class AnalysisRunResponse(BaseModel):
    analysis_id: UUID
    analysis_name: str
    status: str
    mode: str
    disease_id: str | None = None
    current_stage: int | None
    stage_results: dict[str, Any]
    parameters: dict[str, Any] | None
    created_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None = None
    error_message: str | None
