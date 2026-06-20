"""Disease ORM models (read)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Disease(Base):
    __tablename__ = "diseases"

    disease_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    canonical_key: Mapped[str] = mapped_column(String, nullable=False)
    disease_name: Mapped[str | None] = mapped_column(String)
    ontology_id: Mapped[str | None] = mapped_column(String)
    ontology_source: Mapped[str | None] = mapped_column(String)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_url: Mapped[str | None] = mapped_column(String)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DiseaseAlias(Base):
    __tablename__ = "disease_aliases"

    disease_alias_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    alias_name: Mapped[str | None] = mapped_column(String)
    alias_key: Mapped[str | None] = mapped_column(String)
    alias_type: Mapped[str | None] = mapped_column(String)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
