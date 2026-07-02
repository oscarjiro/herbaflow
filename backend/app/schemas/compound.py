"""Compound resolution DTOs (manual-input request/response shapes)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class CompoundInput(BaseModel):
    type: Literal["smiles", "inchikey"] | None = None
    value: str


class ResolvedCompound(BaseModel):
    compound_id: uuid.UUID
    canonical_name: str | None
    pubchem_cid: str | None = None
    validation_status: str  # externally_validated | structure_only


class FailedInput(BaseModel):
    value: str
    reason: str
    line: int | None = None


class ValidateRequest(BaseModel):
    inputs: list[CompoundInput]


class ValidateResponse(BaseModel):
    resolved: list[ResolvedCompound]
    failed: list[FailedInput]
