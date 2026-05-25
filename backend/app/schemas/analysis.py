from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID
from datetime import datetime
from typing import Any, Literal


class ResetFromRequest(BaseModel):
    params: dict[str, Any] | None = None   # e.g. {"adme": {"max_mw": 600}}
    rerun: bool = False


class ApproveRequest(BaseModel):
    param_overrides: dict[str, Any] | None = None   # e.g. {"target": {"min_pchembl": 6.0}}


class CreateAnalysisRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable label for the analysis run",
    )
    mode: Literal["guided", "auto"] = "guided"
    plant_ids: list[str] = Field(default_factory=list)
    disease_ids: list[str] = Field(min_length=1, description="At least one disease is required")
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class AnalysisStatusResponse(BaseModel):
    analysis_id: UUID
    status: str
    mode: str
    current_stage: int | None
    progress: dict[str, int]
    created_at: datetime | None
    updated_at: datetime | None
    error_message: str | None = None
    expires_at: datetime | None = None


class AnalysisRunResponse(BaseModel):
    analysis_id: UUID
    analysis_name: str
    status: str
    mode: str
    disease_id: str | None = None
    current_stage: int | None
    stage_results: dict[str, Any]
    parameters: dict[str, Any] | None
    created_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None = None
    error_message: str | None


class AddUserTargetRequest(BaseModel):
    gene_symbol: str | None = None
    uniprot_id: str | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "AddUserTargetRequest":
        if not self.gene_symbol and not self.uniprot_id:
            raise ValueError("Provide at least one of gene_symbol or uniprot_id")
        return self


class AddUserTargetResponse(BaseModel):
    target_id: str
    gene_symbol: str
    uniprot_id: str | None
    protein_name: str | None


class InjectCompoundsRequest(BaseModel):
    compounds: list[str] = Field(
        min_length=1,
        max_length=100,
        description="SMILES or InChI strings, 1–100 items",
    )


class InjectCompoundsResponse(BaseModel):
    injected: int          # number successfully validated and stored
    failed: list[str]      # raw input strings that failed PubChem validation


class InjectTargetsRequest(BaseModel):
    targets: list[str] = Field(
        min_length=1,
        max_length=200,
        description="Gene symbols or UniProt accessions, 1–200 items",
    )


class InjectTargetsResponse(BaseModel):
    injected: int          # number successfully validated and stored
    failed: list[str]      # raw input strings that failed UniProt validation
