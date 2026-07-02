"""Plant wire DTOs."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class PlantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plant_id: uuid.UUID
    canonical_scientific_name: str | None
    family_name: str | None
    matched_alias: str | None = None
    compound_count: int = 0
