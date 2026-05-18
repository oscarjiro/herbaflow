# backend/app/models/compound.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class Compound(SQLModel, table=True):
    __tablename__ = "compounds"

    compound_id: str = Field(primary_key=True)
    canonical_key: str = Field(unique=True)
    canonical_name: str
    inchi_key: Optional[str] = None
    smiles: Optional[str] = None
    cas_id: Optional[str] = None
    pubchem_cid: Optional[str] = None
    chembl_id: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    tpsa: Optional[float] = None
    logp: Optional[float] = None
    hbond_donors: Optional[int] = None
    hbond_acceptors: Optional[int] = None
    rotatable_bonds: Optional[int] = None
    num_ro5_violations: Optional[int] = None
    qed_score: Optional[float] = None
    np_likeness_score: Optional[float] = None
    lipinski_source: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id", sa_type=PGUUID(as_uuid=True))
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, foreign_key="import_batches.batch_id", sa_type=PGUUID(as_uuid=True))
    retrieved_at: Optional[datetime] = None
    confidence: Optional[float] = None


class CompoundAlias(SQLModel, table=True):
    __tablename__ = "compound_aliases"

    compound_alias_id: str = Field(primary_key=True)
    compound_id: str = Field(foreign_key="compounds.compound_id")
    alias_name: str
    alias_key: Optional[str] = None
    alias_type: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id", sa_type=PGUUID(as_uuid=True))
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, foreign_key="import_batches.batch_id", sa_type=PGUUID(as_uuid=True))
    retrieved_at: Optional[datetime] = None


class PlantCompound(SQLModel, table=True):
    __tablename__ = "plant_compounds"

    plant_compound_id: str = Field(primary_key=True)
    plant_id: str = Field(foreign_key="plants.plant_id")
    compound_id: str = Field(foreign_key="compounds.compound_id")
    source_plant_raw_id: Optional[str] = None
    source_compound_raw_id: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id", sa_type=PGUUID(as_uuid=True))
    evidence_type: Optional[str] = None
    confidence: Optional[float] = None
    retrieved_at: Optional[datetime] = None
