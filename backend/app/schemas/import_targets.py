from pydantic import BaseModel, field_validator
import re


class STPTarget(BaseModel):
    uniprot_id: str
    gene_symbol: str
    probability: float

    @field_validator("uniprot_id")
    @classmethod
    def validate_uniprot(cls, v: str) -> str:
        # Basic UniProt accession format check: 6–10 uppercase alphanumeric chars
        if not re.match(r"^[A-Z0-9]{6,10}$", v.strip()):
            raise ValueError(f"Invalid UniProt accession format: {v!r}")
        return v.strip()


class ImportTargetsRequest(BaseModel):
    compound_id: str
    targets: list[STPTarget]


class ImportTargetsResponse(BaseModel):
    imported: int
    skipped: int
