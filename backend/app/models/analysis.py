# backend/app/models/analysis.py
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime, ForeignKey
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
    # These columns are timestamptz in Postgres. Declare them WITH TIME ZONE so the
    # ORM binds/returns timezone-aware UTC datetimes (matches now_utc()); no schema change.
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    expires_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
