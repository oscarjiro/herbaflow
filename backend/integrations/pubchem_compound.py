"""PubChem REST API client for compound validation and ADME computation.

Used by T4.3 manual compound input to validate SMILES/InChI strings,
retrieve canonical properties, and compute Lipinski ADME criteria.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from app.services.canonicalize import compound_canonical_key, make_compound_id

from integrations._retry import ServiceUnavailableError, with_retry

logger = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Properties to request from PubChem
_PROPERTY_LIST = (
    "IUPACName,MolecularWeight,MolecularFormula,"
    "InChIKey,XLogP,HBondDonorCount,HBondAcceptorCount,RotatableBondCount"
)


def _is_inchi(s: str) -> bool:
    return s.strip().startswith("InChI=")


def compute_adme(props: dict) -> dict:
    """Compute ADME/Lipinski criteria from PubChem property values.

    PubChem REST returns numeric values as strings. Parseable values are coerced
    to float/int; any property that is absent or unparseable is returned as
    ``None`` — a missing measurement is never represented by a placeholder
    number. The 999/99 Lipinski-fail sentinels are applied only inside the
    ``lipinski_pass`` boolean and never appear in the returned numeric fields.

    Returns ``insufficient_data: True`` when all of mw/xlogp/hbd/hba are missing;
    such a compound must NOT auto-pass Lipinski filters.
    """
    def _float(val) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _int(val) -> int | None:
        if val is None:
            return None
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return None

    mw = _float(props.get("MolecularWeight"))
    xlogp = _float(props.get("XLogP"))
    hbd = _int(props.get("HBondDonorCount"))
    hba = _int(props.get("HBondAcceptorCount"))
    rotatable = _int(props.get("RotatableBondCount"))

    # No core data at all → cannot evaluate drug-likeness; must not auto-pass.
    insufficient_data = all(v is None for v in (mw, xlogp, hbd, hba))

    if insufficient_data:
        lipinski_pass = False
    else:
        # A missing individual property fails its own check. The 999/99 sentinels
        # stay local to this boolean and never escape as stored numeric values.
        lipinski_pass = (
            (mw if mw is not None else 999) <= 500
            and (xlogp if xlogp is not None else 99) <= 5
            and (hbd if hbd is not None else 99) <= 5
            and (hba if hba is not None else 99) <= 10
        )

    return {
        "mw": mw,
        "xlogp": xlogp,
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rotatable,
        "lipinski_pass": lipinski_pass,
        "adme_pass": lipinski_pass,
        "insufficient_data": insufficient_data,
    }


async def _fetch_cid(
    structure: str,
    client: httpx.AsyncClient,
) -> int | None:
    """Resolve a SMILES or InChI string to a numeric PubChem CID.

    Uses POST /compound/smiles/cids/JSON for SMILES and
    POST /compound/inchi/cids/JSON for InChI. POST avoids URL-encoding
    breakage on SMILES with double-bond/stereo notation.

    Returns the first CID as an integer, or None if not found / on error.
    """
    if _is_inchi(structure):
        url = f"{PUBCHEM_BASE}/compound/inchi/cids/JSON"

        async def _post_cid() -> httpx.Response:
            r = await client.post(url, data={"inchi": structure})
            if r.status_code in (400, 404):
                return r
            r.raise_for_status()
            return r

        try:
            resp = await with_retry(_post_cid, service_name="PubChem")
        except (ServiceUnavailableError, httpx.HTTPError) as e:
            logger.warning("PubChem CID lookup failed for InChI input: %s", e)
            return None
    else:
        url = f"{PUBCHEM_BASE}/compound/smiles/cids/JSON"

        async def _post_cid() -> httpx.Response:
            r = await client.post(url, data={"smiles": structure})
            if r.status_code in (400, 404):
                return r
            r.raise_for_status()
            return r

        try:
            resp = await with_retry(_post_cid, service_name="PubChem")
        except (ServiceUnavailableError, httpx.HTTPError) as e:
            logger.warning("PubChem CID lookup failed for SMILES input %r: %s", structure[:50], e)
            return None

    if resp.status_code in (400, 404):
        return None

    try:
        data = resp.json()
    except Exception:
        return None

    cids = (data.get("IdentifierList") or {}).get("CID") or []
    return cids[0] if cids else None


async def validate_compound(
    structure: str,
    client: httpx.AsyncClient,
) -> dict | None:
    """Validate a SMILES or InChI string via PubChem and return compound data.

    Returns a compound dict on success, or None if the compound cannot be found.

    The returned dict has the following keys:
    - compound_id: deterministic UUID v5 string
    - pubchem_cid: numeric PubChem CID as a string (e.g. "2244"), used for DB caching
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

    # Step 1: resolve the numeric CID first.  This gives us a stable identifier
    # for DB caching and lets us fetch properties by CID (avoiding URL-encoding
    # issues with complex SMILES strings on the property path).
    cid = await _fetch_cid(structure, client)
    if cid is None:
        # Compound not in PubChem — cannot validate
        return None

    # Step 2: fetch properties by CID (always succeeds if CID is valid)
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/property/{_PROPERTY_LIST}/JSON"

    async def _get_props() -> httpx.Response:
        r = await client.get(url)
        if r.status_code in (400, 404):
            return r
        r.raise_for_status()
        return r

    try:
        resp = await with_retry(_get_props, service_name="PubChem")
    except ServiceUnavailableError as e:
        logger.error("PubChem unavailable during compound validation: %s", e)
        return None
    except httpx.HTTPError as e:
        logger.warning("PubChem property fetch failed for CID %s: %s", cid, e)
        return None

    if resp.status_code in (400, 404):
        return None

    try:
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

    compound_id = make_compound_id(inchikey)
    adme = compute_adme(props)

    return {
        "compound_id": compound_id,
        "canonical_key": compound_canonical_key(inchikey),
        "pubchem_cid": str(cid),  # string to match existing cache data conventions
        "inchikey": inchikey,
        "iupac_name": iupac_name,
        "molecular_formula": molecular_formula,
        "molecular_weight": adme["mw"],
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
