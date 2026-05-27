from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID
from datetime import datetime
from typing import Any, Literal


def _validate_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate critical numeric parameter bounds in a params/parameters dict.

    Enforces bounds only for params that cause runtime errors when violated:
    - enrichment.fdr_threshold in (0, 1]  → log(0) in Stage 8
    - adme.max_mw > 0                     → divide-by-zero / nonsensical filter
    - target.min_pchembl in [0, 14]       → invalid ChEMBL range
    - target.min_assay_confidence in [0, 9] → invalid ChEMBL confidence
    - hub_genes.top_n >= 1               → empty hub list
    - ppi.min_confidence in (0, 1]        → STRING returns everything
    """
    if not params:
        return params

    errors: list[str] = []

    enrichment = params.get("enrichment", {}) or {}
    fdr = enrichment.get("fdr_threshold")
    if fdr is not None and not (0 < fdr <= 1):
        errors.append("enrichment.fdr_threshold must be in (0, 1]")

    adme = params.get("adme", {}) or {}
    max_mw = adme.get("max_mw")
    if max_mw is not None and max_mw <= 0:
        errors.append("adme.max_mw must be > 0")

    target = params.get("target", {}) or {}
    min_pchembl = target.get("min_pchembl")
    if min_pchembl is not None and not (0 <= min_pchembl <= 14):
        errors.append("target.min_pchembl must be in [0, 14]")
    min_assay = target.get("min_assay_confidence")
    if min_assay is not None and not (0 <= min_assay <= 9):
        errors.append("target.min_assay_confidence must be in [0, 9]")

    hub_genes = params.get("hub_genes", {}) or {}
    top_n = hub_genes.get("top_n")
    if top_n is not None and top_n < 1:
        errors.append("hub_genes.top_n must be >= 1")

    ppi = params.get("ppi", {}) or {}
    min_conf = ppi.get("min_confidence")
    if min_conf is not None and not (0 < min_conf <= 1):
        errors.append("ppi.min_confidence must be in (0, 1]")

    if errors:
        raise ValueError("; ".join(errors))

    return params


class ResetFromRequest(BaseModel):
    params: dict[str, Any] | None = None   # e.g. {"adme": {"max_mw": 600}}
    rerun: bool = False

    @field_validator("params")
    @classmethod
    def validate_params(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_params(v)


class ApproveRequest(BaseModel):
    param_overrides: dict[str, Any] | None = None   # e.g. {"target": {"min_pchembl": 6.0}}

    @field_validator("param_overrides")
    @classmethod
    def validate_param_overrides(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_params(v)


class CreateAnalysisRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable label for the analysis run",
    )
    mode: Literal["guided", "auto"] = "guided"
    plant_ids: list[str] = Field(default_factory=list)
    disease_ids: list[str] = Field(
        default_factory=list,
        description="At least one disease is required, unless _disease_input_mode is manual_targets",
    )
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _validate_params(v) or v

    @model_validator(mode="after")
    def disease_ids_required_unless_manual(self) -> "CreateAnalysisRequest":
        is_manual_disease = (
            (self.parameters or {}).get("_disease_input_mode") == "manual_targets"
        )
        if not is_manual_disease and len(self.disease_ids) == 0:
            raise ValueError(
                "disease_ids: at least one disease is required "
                "(or set _disease_input_mode=manual_targets in parameters)"
            )
        return self


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
