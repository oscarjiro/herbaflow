"""PubChem REST API client for compound validation and ADME computation.

Used by T4.3 manual compound input to validate SMILES/InChI strings,
retrieve canonical properties, and compute Lipinski ADME criteria.
"""
from __future__ import annotations

import logging
import uuid
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Properties to request from PubChem
_PROPERTY_LIST = (
    "IUPACName,MolecularWeight,MolecularFormula,"
    "InChIKey,XLogP,HBondDonorCount,HBondAcceptorCount,RotatableBondCount"
)


def _is_inchi(s: str) -> bool:
    return s.strip().startswith("InChI=")


def make_compound_id(inchikey: str) -> str:
    """Return a deterministic UUID v5 for a compound, keyed on its InChIKey."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"inchikey:{inchikey}"))


def compute_adme(props: dict) -> dict:
    """Compute ADME/Lipinski criteria from PubChem property values.

    Uses Lipinski's Rule of Five:
    - MW <= 500
    - XLogP <= 5
    - HBD <= 5
    - HBA <= 10
    """
    mw = props.get("MolecularWeight", 999)
    xlogp = props.get("XLogP", 99)
    hbd = props.get("HBondDonorCount", 99)
    hba = props.get("HBondAcceptorCount", 99)
    rotatable = props.get("RotatableBondCount", 99)

    lipinski_pass = mw <= 500 and xlogp <= 5 and hbd <= 5 and hba <= 10

    return {
        "mw": mw,
        "xlogp": xlogp,
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rotatable,
        "lipinski_pass": lipinski_pass,
        "adme_pass": lipinski_pass,  # simplified: ADME pass == Lipinski pass
    }


async def validate_compound(
    structure: str,
    client: httpx.AsyncClient,
) -> dict | None:
    """Validate a SMILES or InChI string via PubChem and return compound data.

    Returns a compound dict on success, or None if the compound cannot be found.

    The returned dict has the following keys:
    - compound_id: deterministic UUID v5 string
    - inchikey: InChIKey string
    - iupac_name: IUPAC name (may be empty string)
    - molecular_formula: molecular formula
    - molecular_weight: float
    - canonical_name: IUPAC name or raw input as fallback
    - plant_ids: [] (empty — manual input has no plant source)
    - adme fields (mw, xlogp, hbd, hba, rotatable_bonds, lipinski_pass, adme_pass)
    - is_pains_positive: False (not computed here)
    - is_np_exception: False
    """
    structure = structure.strip()
    if not structure:
        return None

    if _is_inchi(structure):
        input_type = "inchi"
        # PubChem requires InChI in the path but it can contain slashes — use POST
        # For simplicity, use the URL-encoded GET approach with inchi type
        encoded = quote(structure, safe="")
        url = f"{PUBCHEM_BASE}/compound/inchi/property/{_PROPERTY_LIST}/JSON"
        try:
            resp = await client.post(url, data={"inchi": structure})
        except httpx.HTTPError as e:
            logger.warning("PubChem validation failed for input %r: %s", structure[:50], e)
            return None
    else:
        # Treat as SMILES
        encoded = quote(structure, safe="")
        url = f"{PUBCHEM_BASE}/compound/smiles/{encoded}/property/{_PROPERTY_LIST}/JSON"
        try:
            resp = await client.get(url)
        except httpx.HTTPError as e:
            logger.warning("PubChem validation failed for input %r: %s", structure[:50], e)
            return None

    if resp.status_code == 404 or resp.status_code == 400:
        return None

    try:
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    props_list = (data.get("PropertyTable") or {}).get("Properties") or []
    if not props_list:
        return None

    props = props_list[0]
    inchikey = props.get("InChIKey", "")
    if not inchikey:
        return None

    iupac_name = props.get("IUPACName", "") or ""
    molecular_formula = props.get("MolecularFormula", "") or ""
    molecular_weight = float(props.get("MolecularWeight") or 0)

    compound_id = make_compound_id(inchikey)
    adme = compute_adme(props)

    return {
        "compound_id": compound_id,
        "inchikey": inchikey,
        "iupac_name": iupac_name,
        "molecular_formula": molecular_formula,
        "molecular_weight": molecular_weight,
        "canonical_name": iupac_name or structure,
        "plant_ids": [],
        # ADME fields (stage2-compatible keys)
        "adme_pass": adme["adme_pass"],
        "is_np_exception": False,
        "is_pains_positive": False,
        "logp": adme["xlogp"],
        # TPSA is not available from the PubChem property endpoint used here.
        # stage2_adme.filter_compounds() already guards with `if c.tpsa is not None`,
        # so None is safe — the Veber TPSA check is simply skipped for manual compounds.
        "tpsa": None,
        "hbond_donors": adme["hbd"],
        "hbond_acceptors": adme["hba"],
        "np_likeness_score": None,
        "rotatable_bonds": adme["rotatable_bonds"],
        # Keep raw ADME dict fields too for stage1/stage2 result building
        "mw": adme["mw"],
        "xlogp": adme["xlogp"],
        "hbd": adme["hbd"],
        "hba": adme["hba"],
        "lipinski_pass": adme["lipinski_pass"],
    }


async def validate_compounds_batch(
    structures: list[str],
    client: httpx.AsyncClient,
) -> tuple[list[dict], list[str]]:
    """Validate a list of SMILES/InChI strings against PubChem.

    Returns (validated_compounds, failed_inputs) where:
    - validated_compounds: list of compound dicts for successfully validated inputs
    - failed_inputs: list of raw input strings that failed validation (404, error, etc.)

    Deduplicates by InChIKey — if two inputs resolve to the same compound,
    only the first occurrence is kept.
    """
    import asyncio

    async def _validate_one(structure: str) -> tuple[str, dict | None]:
        result = await validate_compound(structure, client)
        return (structure, result)

    tasks = [_validate_one(s) for s in structures if s.strip()]
    results = await asyncio.gather(*tasks)

    seen_inchikeys: set[str] = set()
    validated: list[dict] = []
    failed: list[str] = []

    for raw_input, compound in results:
        if compound is None:
            failed.append(raw_input)
        elif compound["inchikey"] in seen_inchikeys:
            # Duplicate — count as failed (duplicate)
            pass
        else:
            seen_inchikeys.add(compound["inchikey"])
            validated.append(compound)

    return validated, failed
