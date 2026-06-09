"""RDKit structure→identity helpers (parse SMILES → InChIKey + canonical SMILES). Identity only."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")  # silence parse warnings; we report via return value

_INCHIKEY = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


@dataclass(frozen=True)
class StructureIdentity:
    inchikey: str
    canonical_smiles: str


def is_inchikey(token: str) -> bool:
    return bool(_INCHIKEY.match(token.strip()))


def identity_from_smiles(smiles: str) -> StructureIdentity | None:
    """Return identity for a valid SMILES, or None if RDKit cannot parse it."""
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        return None
    inchikey = Chem.MolToInchiKey(mol)
    if not inchikey:  # no InChI for this structure (rare; e.g. certain organometallics)
        return None
    return StructureIdentity(inchikey=inchikey, canonical_smiles=Chem.MolToSmiles(mol))
