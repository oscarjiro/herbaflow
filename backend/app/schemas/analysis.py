import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from uuid import UUID
from datetime import datetime
from typing import Any

from app.contracts import ANALYSIS_MODES

# ---------------------------------------------------------------------------
# Format validators — UniProt accession and HGNC gene symbol
# ---------------------------------------------------------------------------

# UniProt accession: HUPO-PSI standard two-pattern format.
#   6-char legacy:  [OPQ][0-9][A-Z0-9]{3}[0-9]
#   10-char new:    [A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}
UNIPROT_ACCESSION_RE = re.compile(
    r'^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$'
)

# HGNC gene symbol: uppercase letter start, 1–25 chars, A-Z / 0-9 / hyphen only.
GENE_SYMBOL_RE = re.compile(r'^[A-Z][A-Z0-9\-]{0,24}$')


# STRING-DB standard confidence thresholds (Low / Medium / High / Very High)
STRING_CONFIDENCE_PRESETS = {0.15, 0.40, 0.70, 0.90}


# ---------------------------------------------------------------------------
# Strict nested pipeline-parameter contract.
# Every group and field is OPTIONAL (overrides on top of backend defaults), so the
# same model serves create (full set), approve.param_overrides, and reset.params
# (partial). extra="forbid" makes a flat or unknown-key payload a 422 instead of a
# silent drop. Field names/ranges mirror shared/contracts/analysis.json and the
# PipelineConfig dataclass (analysis/models.py); test_contract_param_agreement guards drift.
# ---------------------------------------------------------------------------

class _StrictParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdmeParamsIn(_StrictParams):
    max_mw: float | None = Field(default=None, gt=0)
    max_logp: float | None = None
    max_hbd: int | None = Field(default=None, ge=0)
    max_hba: int | None = Field(default=None, ge=0)
    max_tpsa: float | None = Field(default=None, ge=0)
    max_rotatable_bonds: int | None = Field(default=None, ge=0)
    apply_veber: bool | None = None
    np_exception_threshold: float | None = Field(default=None, ge=0, le=1)
    apply_adme_to_manual: bool | None = None


class TargetParamsIn(_StrictParams):
    min_pchembl: float | None = Field(default=None, ge=0, le=14)
    human_only: bool | None = None
    min_assay_confidence: int | None = Field(default=None, ge=0, le=9)


class DiseaseTargetParamsIn(_StrictParams):
    min_score: float | None = Field(default=None, ge=0, le=1)


class PpiParamsIn(_StrictParams):
    min_confidence: float | None = None
    community_resolution: float | None = Field(default=None, ge=0.1, le=3.0)

    @field_validator("min_confidence")
    @classmethod
    def confidence_in_presets(cls, v: float | None) -> float | None:
        if v is not None and v not in STRING_CONFIDENCE_PRESETS:
            raise ValueError(
                f"ppi.min_confidence must be one of {sorted(STRING_CONFIDENCE_PRESETS)} "
                "(STRING-DB standard levels: Low=0.15, Medium=0.40, High=0.70, Very High=0.90)"
            )
        return v


class HubGeneParamsIn(_StrictParams):
    top_n: int | None = Field(default=None, ge=1)
    use_hub_bottleneck: bool | None = None


class EnrichmentParamsIn(_StrictParams):
    fdr_threshold: float | None = Field(default=None, gt=0, le=1)
    sources: list[str] | None = Field(default=None, min_length=1)


class AnalysisParameters(_StrictParams):
    adme: AdmeParamsIn | None = None
    target: TargetParamsIn | None = None
    disease_targets: DiseaseTargetParamsIn | None = None
    ppi: PpiParamsIn | None = None
    hub_genes: HubGeneParamsIn | None = None
    enrichment: EnrichmentParamsIn | None = None

# Input size limits — based on published network pharmacology study scales.
# Plants:    90%+ of NP studies use ≤ 20 herbs; Indonesian jamu formulas 3–15 plants.
#            Li S et al. (2014) Evid Based Complement Alternat Med;
#            Jiang Y et al. (2021) systematic review of TCM-NP studies.
# Compounds: 20 plants × ~250 KNApSAcK compounds/plant ≈ 5,000 pre-ADME — internal
#            consistency ceiling. Zhou Y et al. (2019) Evid Based Complement Alternat Med.
# Targets (compound-side): Covers the entire human druggable proteome (~4,719 proteins;
#            Finan C et al. (2017) Sci Transl Med). Compound targets intersect disease
#            targets at Stage 5 before reaching STRING-DB, so STRING input is the overlap
#            (typically 50–500 genes), not the raw target count.
#            Szklarczyk D et al. (2023) STRING v12, Nucleic Acids Res;
#            Traag VA et al. (2019) Leiden algorithm, Sci Rep.
# Targets (disease-side): Open Targets single-disease associations 200–2,000;
#            Ochoa et al. (2021) Nucleic Acids Res (Open Targets Platform);
#            Piñero et al. (2020) Nucleic Acids Res (DisGeNET v7).
SOFT_CAP_PLANTS = 10
HARD_CAP_PLANTS = 20
SOFT_CAP_MANUAL_COMPOUNDS = 1000
HARD_CAP_MANUAL_COMPOUNDS = 5000
SOFT_CAP_MANUAL_TARGETS = 500
HARD_CAP_MANUAL_TARGETS = 5000
SOFT_CAP_DISEASE_TARGETS = 500
HARD_CAP_DISEASE_TARGETS = 2000


def _validate_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate critical numeric parameter bounds in a params/parameters dict.

    Enforces bounds only for params that cause runtime errors when violated:
    - enrichment.fdr_threshold in (0, 1]  → log(0) in Stage 8
    - adme.max_mw > 0                     → divide-by-zero / nonsensical filter
    - target.min_pchembl in [0, 14]       → invalid ChEMBL range
    - target.min_assay_confidence in [0, 9] → invalid ChEMBL confidence
    - hub_genes.top_n >= 1               → empty hub list
    - ppi.min_confidence in STRING_CONFIDENCE_PRESETS → STRING-DB standard levels
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
    if min_conf is not None and min_conf not in STRING_CONFIDENCE_PRESETS:
        errors.append(
            f"ppi.min_confidence must be one of {sorted(STRING_CONFIDENCE_PRESETS)} "
            "(STRING-DB standard confidence levels: Low=0.15, Medium=0.40, High=0.70, Very High=0.90)"
        )
    comm_res = ppi.get("community_resolution")
    if comm_res is not None and not (0.1 <= comm_res <= 3.0):
        errors.append("ppi.community_resolution must be in [0.1, 3.0]")

    injected_disease = params.get("_injected_disease_targets")
    if injected_disease is not None and len(injected_disease) > HARD_CAP_DISEASE_TARGETS:
        errors.append(
            f"_injected_disease_targets: at most {HARD_CAP_DISEASE_TARGETS} disease targets allowed "
            f"(OpenTargets dataset scale; Ochoa et al. 2021 Nucleic Acids Res)"
        )

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
    mode: str = Field(
        default="guided",
        json_schema_extra={"enum": list(ANALYSIS_MODES)},
    )
    plant_ids: list[str] = Field(
        default_factory=list,
        max_length=HARD_CAP_PLANTS,
        description=f"KNApSAcK plant IDs. Hard limit: {HARD_CAP_PLANTS} plants per analysis.",
    )
    disease_id: str | None = Field(
        default=None,
        description="Exactly one disease per analysis. Required unless _disease_input_mode is manual_targets.",
    )
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("mode")
    @classmethod
    def mode_in_contract(cls, v: str) -> str:
        if v not in ANALYSIS_MODES:
            raise ValueError(f"mode must be one of {sorted(ANALYSIS_MODES)}")
        return v

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
    def disease_id_required_unless_manual(self) -> "CreateAnalysisRequest":
        is_manual_disease = (
            (self.parameters or {}).get("_disease_input_mode") == "manual_targets"
        )
        if not is_manual_disease and not self.disease_id:
            raise ValueError(
                "disease_id: a disease is required "
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

    @field_validator("uniprot_id")
    @classmethod
    def validate_uniprot_format(cls, v: str | None) -> str | None:
        if v is not None and not UNIPROT_ACCESSION_RE.match(v):
            raise ValueError(
                f"Invalid UniProt accession format: {v!r}. "
                "Expected HUPO-PSI format, e.g. P04637 or Q9Y6I3."
            )
        return v

    @field_validator("gene_symbol")
    @classmethod
    def validate_gene_symbol_format(cls, v: str | None) -> str | None:
        if v is not None and not GENE_SYMBOL_RE.match(v):
            raise ValueError(
                f"Invalid HGNC gene symbol: {v!r}. "
                "Gene symbols must be uppercase, start with a letter, "
                "1–25 characters (A-Z, 0-9, hyphen), e.g. TP53 or HIF-1A."
            )
        return v

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
        max_length=HARD_CAP_MANUAL_COMPOUNDS,
        description=f"SMILES or InChI strings, 1–{HARD_CAP_MANUAL_COMPOUNDS} items",
    )


class InjectCompoundsResponse(BaseModel):
    injected: int                           # number successfully validated and stored
    failed: list[str]                       # raw input strings that failed PubChem validation
    duplicates_removed: int = 0             # inputs dropped due to deduplication
    duplicate_names: list[str] = Field(default_factory=list)  # the dropped raw inputs
    cached: int = 0                         # compounds persisted to DB cache (have PubChem CID)


class AddUserCompoundRequest(BaseModel):
    smiles: str | None = None
    inchi: str | None = None

    @field_validator("smiles")
    @classmethod
    def validate_smiles_minimum(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) < 3:
            raise ValueError(
                f"SMILES string is too short ({len(v)} chars); minimum length is 3."
            )
        if not v.isascii() or not v.isprintable():
            raise ValueError(
                "SMILES must contain only printable ASCII characters."
            )
        return v

    @model_validator(mode="after")
    def at_least_one(self) -> "AddUserCompoundRequest":
        if not self.smiles and not self.inchi:
            raise ValueError("Provide at least one of smiles or inchi")
        return self


class AddUserCompoundResponse(BaseModel):
    compound_id: str
    canonical_name: str
    smiles: str | None = None


class InjectTargetsRequest(BaseModel):
    targets: list[str] = Field(
        min_length=1,
        max_length=HARD_CAP_MANUAL_TARGETS,
        description=f"Gene symbols or UniProt accessions, 1–{HARD_CAP_MANUAL_TARGETS} items",
    )
    skip_validation: bool = Field(
        default=False,
        description=(
            "Lenient mode: skip UniProt validation for gene symbols and instead "
            "normalize them offline to canonical HGNC symbols (unknowns kept and "
            "flagged). UniProt accessions are still resolved via UniProt."
        ),
    )


class InjectTargetsResponse(BaseModel):
    injected: int                                                    # number successfully validated and stored
    failed: list[str]                                                # raw input strings that failed UniProt validation
    duplicates_removed: int = 0                                      # inputs dropped due to deduplication
    duplicate_names: list[str] = Field(default_factory=list)         # labels for the dropped entries
    cached: int = 0                                                  # targets persisted to DB cache (validated, have UniProt accession)
    normalized: list[dict] = Field(default_factory=list)            # [{"from": input, "to": canonical}] HGNC alias/prev resolutions
    unrecognized: list[str] = Field(default_factory=list)           # lenient inputs kept as-is (not found in HGNC / UniProt)
