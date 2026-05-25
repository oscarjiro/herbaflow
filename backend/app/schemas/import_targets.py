from pydantic import BaseModel, field_validator
import re


class STPTarget(BaseModel):
    uniprot_id: str
    gene_symbol: str
    probability: float

    @field_validator("uniprot_id")
    @classmethod
    def validate_uniprot(cls, v: str) -> str:
        v = v.strip().upper()  # normalize before validating
        if not re.match(r"^[A-Z0-9]{6,10}$", v):
            raise ValueError(f"Invalid UniProt accession format: {v!r}")
        return v

    @field_validator("gene_symbol")
    @classmethod
    def normalize_gene_symbol(cls, v: str) -> str:
        return v.strip().upper()


class ImportTargetsRequest(BaseModel):
    compound_id: str
    targets: list[STPTarget]


class ImportTargetsResponse(BaseModel):
    imported: int
    skipped: int
