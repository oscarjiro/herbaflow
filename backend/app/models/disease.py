# backend/app/models/disease.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class Disease(SQLModel, table=True):
    __tablename__ = "diseases"

    disease_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    canonical_key: str = Field(unique=True)
    disease_name: str
    ontology_id: Optional[str] = None
    ontology_source: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class DiseaseAlias(SQLModel, table=True):
    __tablename__ = "disease_aliases"

    disease_alias_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    disease_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("diseases.disease_id")))
    alias_name: str
    alias_key: Optional[str] = None
    alias_type: Optional[str] = None
    retrieved_at: Optional[datetime] = None
