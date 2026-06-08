"""Disease wire DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DiseaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    disease_id: uuid.UUID
    canonical_key: str
    disease_name: str | None
    ontology_id: str | None
    ontology_source: str | None
    source_url: str | None
    retrieved_at: datetime | None
