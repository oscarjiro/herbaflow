"""Compound ORM model (resolution reads/writes; subset used by Stage 1)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Compound(Base):
    __tablename__ = "compounds"

    compound_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    canonical_name: Mapped[str | None] = mapped_column(String)
    inchi_key: Mapped[str | None] = mapped_column(String)
    connectivity_key: Mapped[str | None] = mapped_column(String)
    smiles: Mapped[str | None] = mapped_column(String)
    cas_id: Mapped[str | None] = mapped_column(String)
    pubchem_cid: Mapped[str | None] = mapped_column(String)
    chembl_id: Mapped[str | None] = mapped_column(String)
    molecular_formula: Mapped[str | None] = mapped_column(String)
    molecular_weight: Mapped[float | None] = mapped_column(Float)
    tpsa: Mapped[float | None] = mapped_column(Float)
    logp: Mapped[float | None] = mapped_column(Float)
    hbond_donors: Mapped[int | None] = mapped_column(Integer)
    hbond_acceptors: Mapped[int | None] = mapped_column(Integer)
    rotatable_bonds: Mapped[int | None] = mapped_column(Integer)
    np_likeness_score: Mapped[float | None] = mapped_column(Float)
    num_ro5_violations: Mapped[int | None] = mapped_column(Integer)
    is_pains_positive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validation_status: Mapped[str] = mapped_column(String, nullable=False)
    source_name: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
