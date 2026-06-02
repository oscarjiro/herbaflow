# backend/app/models/target.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class Target(SQLModel, table=True):
    __tablename__ = "targets"

    target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    canonical_key: str = Field(unique=True)
    gene_symbol: Optional[str] = None
    protein_name: Optional[str] = None
    uniprot_accession: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class CompoundTarget(SQLModel, table=True):
    __tablename__ = "compound_targets"

    compound_target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    compound_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("compounds.compound_id")))
    target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("targets.target_id")))
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    prediction_method: Optional[str] = None
    score: Optional[float] = None
    pchembl_value: Optional[float] = None
    retrieved_at: Optional[datetime] = None


class DiseaseTarget(SQLModel, table=True):
    __tablename__ = "disease_targets"

    disease_target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    disease_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("diseases.disease_id")))
    target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("targets.target_id")))
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    association_type: Optional[str] = None
    score: Optional[float] = None
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None
