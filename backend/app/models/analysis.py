# backend/app/models/analysis.py
from typing import Optional, Any
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import Column, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


class AnalysisRun(SQLModel, table=True):
    __tablename__ = "analysis_runs"

    analysis_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True)
    )
    analysis_name: str
    disease_id: Optional[str] = Field(default=None, foreign_key="diseases.disease_id")
    notes: Optional[str] = None
    parameters: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    stage_results: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "pending"
    mode: str = "auto"
    current_stage: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


class TargetRanking(SQLModel, table=True):
    __tablename__ = "target_rankings"
    model_config = ConfigDict(exclude_none=True)

    ranking_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True)
    )
    analysis_id: UUID = Field(foreign_key="analysis_runs.analysis_id", sa_type=PGUUID(as_uuid=True))
    target_id: str = Field(foreign_key="targets.target_id")
    degree_centrality: Optional[float] = None
    betweenness_centrality: Optional[float] = None
    closeness_centrality: Optional[float] = None
    eigenvector_centrality: Optional[float] = None
    disease_association_score: Optional[float] = None
    compound_support_score: Optional[float] = None
    final_score: Optional[float] = None
    rank_position: Optional[int] = None
    created_at: Optional[datetime] = None


class Pathway(SQLModel, table=True):
    __tablename__ = "pathways"

    pathway_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True)
    )
    pathway_code: Optional[str] = None
    pathway_name: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None


class TargetPathway(SQLModel, table=True):
    __tablename__ = "target_pathways"

    target_pathway_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True)
    )
    target_id: str = Field(foreign_key="targets.target_id")
    pathway_id: UUID = Field(foreign_key="pathways.pathway_id", sa_type=PGUUID(as_uuid=True))
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    p_value: Optional[float] = None
    fdr: Optional[float] = None
    confidence: Optional[float] = None
