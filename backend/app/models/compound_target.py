"""CompoundTarget ORM model (pair-grain compound→target edges)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CompoundTarget(Base):
    __tablename__ = "compound_targets"

    compound_target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    compound_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    prediction_method: Mapped[str | None] = mapped_column(String)
    score: Mapped[float | None] = mapped_column(Float)
    pchembl_value: Mapped[float | None] = mapped_column(Float)
    source_url: Mapped[str | None] = mapped_column(String)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    min_pchembl: Mapped[float | None] = mapped_column(Float)
    min_assay_confidence: Mapped[int | None] = mapped_column(Integer)
