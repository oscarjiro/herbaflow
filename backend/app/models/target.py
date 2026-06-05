# backend/app/models/target.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel

# DB columns are `timestamp with time zone`; bind them as tz-aware so the
# tz-aware `now_utc()` value asyncpg receives matches the column type. A naive
# bind raises asyncpg DataError ("can't subtract offset-naive and offset-aware").
_TZ = DateTime(timezone=True)


class Target(SQLModel, table=True):
    __tablename__ = "targets"

    target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    canonical_key: str = Field(unique=True)
    gene_symbol: Optional[str] = None
    protein_name: Optional[str] = None
    uniprot_accession: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = Field(default=None, sa_type=_TZ)


class CompoundTarget(SQLModel, table=True):
    __tablename__ = "compound_targets"

    compound_target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    compound_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("compounds.compound_id")))
    target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("targets.target_id")))
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    prediction_method: Optional[str] = None
    score: Optional[float] = None
    pchembl_value: Optional[float] = None
    retrieved_at: Optional[datetime] = Field(default=None, sa_type=_TZ)


class DiseaseTarget(SQLModel, table=True):
    __tablename__ = "disease_targets"

    disease_target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    disease_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("diseases.disease_id")))
    target_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("targets.target_id")))
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    association_type: Optional[str] = None
    score: Optional[float] = None
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = Field(default=None, sa_type=_TZ)
