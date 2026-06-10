"""DiseaseTarget ORM model (ETL-seeded disease→target associations; Stage 4 reads it)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DiseaseTarget(Base):
    __tablename__ = "disease_targets"

    disease_target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    association_type: Mapped[str | None] = mapped_column(String)
    score: Mapped[float | None] = mapped_column(Float)
    source_url: Mapped[str | None] = mapped_column(String)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
