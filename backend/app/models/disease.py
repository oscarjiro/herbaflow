# backend/app/models/disease.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class Disease(SQLModel, table=True):
    __tablename__ = "diseases"

    disease_id: str = Field(primary_key=True)
    canonical_key: str = Field(unique=True)
    disease_name: str
    ontology_id: Optional[str] = None
    ontology_source: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class DiseaseAlias(SQLModel, table=True):
    __tablename__ = "disease_aliases"

    disease_alias_id: str = Field(primary_key=True)
    disease_id: str = Field(foreign_key="diseases.disease_id")
    alias_name: str
    alias_key: Optional[str] = None
    alias_type: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    retrieved_at: Optional[datetime] = None
