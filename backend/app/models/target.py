"""Target ORM model (canonical human protein/gene; resolution + Stage 3 reads/writes)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Target(Base):
    __tablename__ = "targets"

    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    gene_symbol: Mapped[str | None] = mapped_column(String)
    protein_name: Mapped[str | None] = mapped_column(String)
    uniprot_accession: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
