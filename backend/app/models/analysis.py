# backend/app/models/analysis.py
from typing import Optional, Any
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import Column, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class AnalysisRun(SQLModel, table=True):
    __tablename__ = "analysis_runs"

    analysis_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True)
    )
    analysis_name: str
    disease_id: Optional[str] = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=False), ForeignKey("diseases.disease_id"), nullable=True),
    )
    parameters: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    stage_results: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "pending"
    mode: str = "auto"
    current_stage: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = None
