# backend/app/models/plant.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class Plant(SQLModel, table=True):
    __tablename__ = "plants"

    plant_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    canonical_key: str = Field(unique=True)
    canonical_scientific_name: str
    family_name: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class PlantAlias(SQLModel, table=True):
    __tablename__ = "plant_aliases"

    alias_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), primary_key=True))
    plant_id: str = Field(sa_column=Column(PGUUID(as_uuid=False), ForeignKey("plants.plant_id")))
    alias_name: str
    alias_key: Optional[str] = None
    alias_type: Optional[str] = None
    retrieved_at: Optional[datetime] = None
