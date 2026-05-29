# backend/app/models/plant.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class Plant(SQLModel, table=True):
    __tablename__ = "plants"

    plant_id: str = Field(primary_key=True)
    canonical_key: str = Field(unique=True)
    canonical_scientific_name: str
    authorship: Optional[str] = None
    family_name: Optional[str] = None
    taxonomic_status: Optional[str] = None
    rank: Optional[str] = None
    gbif_usage_key: Optional[int] = None
    gbif_accepted_usage_key: Optional[int] = None
    gbif_species_key: Optional[int] = None
    gbif_genus_key: Optional[int] = None
    gbif_family_key: Optional[int] = None
    gbif_kingdom_key: Optional[int] = None
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    retrieved_at: Optional[datetime] = None
    confidence: Optional[float] = None


class PlantAlias(SQLModel, table=True):
    __tablename__ = "plant_aliases"

    alias_id: str = Field(primary_key=True)
    plant_id: str = Field(foreign_key="plants.plant_id")
    alias_name: str
    alias_key: Optional[str] = None
    alias_type: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    retrieved_at: Optional[datetime] = None
