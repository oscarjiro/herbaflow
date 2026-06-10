"""Target resolution DTOs."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.compound import FailedInput

__all__ = [
    "TargetInput",
    "ResolvedTarget",
    "ValidateTargetsRequest",
    "ValidateTargetsResponse",
    "FailedInput",
]


class TargetInput(BaseModel):
    type: Literal["symbol", "uniprot"] | None = None
    value: str


class ResolvedTarget(BaseModel):
    target_id: uuid.UUID
    canonical_key: str
    gene_symbol: str | None
    uniprot_accession: str | None
    validation_status: str  # externally_validated | db_hit


class ValidateTargetsRequest(BaseModel):
    inputs: list[TargetInput]


class ValidateTargetsResponse(BaseModel):
    resolved: list[ResolvedTarget]
    failed: list[FailedInput]
