from pydantic import BaseModel


class CompoundResponse(BaseModel):
    compound_id: str
    canonical_name: str
    smiles: str | None
    chembl_id: str | None
    pubchem_cid: str | None
    molecular_weight: float | None
    logp: float | None
    tpsa: float | None
    hbond_donors: int | None
    hbond_acceptors: int | None
    rotatable_bonds: int | None
    np_likeness_score: float | None
    num_ro5_violations: int | None
    lipinski_source: str | None
