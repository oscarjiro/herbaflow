"""RDKit / ChEMBL / NP / PAINS property computation for enrichment.

Single home for property derivation, imported by 04_enrich/run.py. Replaces the
former patch_missing_lipinski.py post-pass: 04 computes ADME inline from the
accepted (KNApSAcK-sourced) SMILES.

Ported verbatim (same RDKit descriptor calls, same NP scorer, same PAINS
catalog) from the retired patch_missing_lipinski.py so computed values match
what the old post-hoc patch produced:
  - rdkit_descriptors  <- rdkit_properties() + Descriptors.MolWt (molecular_weight)
  - np_likeness        <- compute_np_score() / _load_np_scorer()
  - check_pains        <- check_pains() / _load_pains_catalog()
  - chembl_detail_by_inchikey <- chembl_properties() + fetch_chembl_molecule()
    + http_cache_path(), but queries ChEMBL /molecule by InChIKey
    (molecule_structures__standard_inchi_key) instead of by chembl_id.
    Confirmed live against ChEMBL (2026-07-13): aspirin InChIKey
    BSYNRYMUTXBXSQ-UHFFFAOYSA-N returns exactly CHEMBL25 with
    qed_weighted=0.55, np_likeness_score=0.12, num_ro5_violations=0.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

log = logging.getLogger("enrich_properties")

CHEMBL_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
REQUEST_TIMEOUT = 30


def _s(val: Any) -> str:
    if val is None or val == "":
        return ""
    return str(val).strip()


# ---------------------------------------------------------------------------
# RDKit descriptors (Lipinski + molecular weight)
# ---------------------------------------------------------------------------


def rdkit_descriptors(smiles: str) -> Optional[Dict[str, str]]:
    """Compute Lipinski descriptors + molecular weight from SMILES using RDKit.

    Returns None on unparseable SMILES (or if RDKit is not importable).
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
    except ImportError:
        log.warning("RDKit not importable — cannot compute descriptors.")
        return None

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    return {
        "logp": _s(round(Descriptors.MolLogP(mol), 4)),
        "hbond_donors": _s(rdMolDescriptors.CalcNumHBD(mol)),
        "hbond_acceptors": _s(rdMolDescriptors.CalcNumHBA(mol)),
        "tpsa": _s(round(Descriptors.TPSA(mol), 4)),
        "rotatable_bonds": _s(rdMolDescriptors.CalcNumRotatableBonds(mol)),
        "molecular_weight": _s(round(Descriptors.MolWt(mol), 4)),
    }


# ---------------------------------------------------------------------------
# Standard InChIKey + connectivity key (cross-DB matching)
# ---------------------------------------------------------------------------


def standard_inchikey(smiles: str) -> str:
    """RDKit **standard** InChIKey from SMILES. Returns "" on unparseable SMILES.

    KNApSAcK publishes some non-standard InChIKeys (``...NA-N``) that never match
    PubChem/ChEMBL (which store standard keys). Recomputing the standard key from the
    scraped SMILES yields the correct, matchable identity for the structure we hold.
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import inchi as rdinchi
    except ImportError:
        log.warning("RDKit not importable — cannot compute standard InChIKey.")
        return ""

    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return ""
    try:
        return rdinchi.MolToInchiKey(mol)
    except Exception:  # noqa: BLE001
        return ""


def connectivity_key(smiles: str) -> str:
    """First InChIKey block (14 chars) of the **tautomer-canonical** form of SMILES.

    Used ONLY for cross-database (ChEMBL/PubChem) connectivity matching, never as
    identity. Curcumin's enol (KNApSAcK) and keto (ChEMBL) tautomers hash to different
    standard keys but canonicalize to the same skeleton, so a connectivity match on this
    key recovers the compound in ChEMBL where an exact-key match misses. Uses RDKit's
    default TautomerEnumerator (bounded max transforms, so it always terminates).
    Returns "" on failure; falls back to the plain standard first block.
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import inchi as rdinchi
        from rdkit.Chem.MolStandardize import rdMolStandardize
    except ImportError:
        return ""

    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return ""
    try:
        enumerator = rdMolStandardize.TautomerEnumerator()
        # Bound enumeration for tractability across the full compound set: some polyphenols
        # enumerate hundreds of tautomers (~20x slower). A 100-tautomer cap yields an identical
        # canonical skeleton for realistic natural products (verified on curcumin + heavy
        # polyphenols) while bounding the worst case to a few ms.
        enumerator.SetMaxTautomers(100)
        canon = enumerator.Canonicalize(mol)
        return rdinchi.MolToInchiKey(canon)[:14]
    except Exception:  # noqa: BLE001
        try:
            return rdinchi.MolToInchiKey(mol)[:14]
        except Exception:  # noqa: BLE001
            return ""


# ---------------------------------------------------------------------------
# RDKit NP-likeness score
# ---------------------------------------------------------------------------

_NP_SCORER_CACHE: Optional[tuple] = None


def _load_np_scorer():
    """Load the RDKit NP scorer model. Returns (npscorer_mod, fscore) or (None, None)."""
    global _NP_SCORER_CACHE
    if _NP_SCORER_CACHE is not None:
        return _NP_SCORER_CACHE

    try:
        import os
        import sys

        from rdkit.Chem import RDConfig

        sys.path.append(os.path.join(RDConfig.RDContribDir, "NP_Score"))
        import npscorer  # type: ignore[import]

        fscore = npscorer.readNPModel()
        log.info(
            "RDKit NP scorer loaded from %s",
            os.path.join(RDConfig.RDContribDir, "NP_Score"),
        )
        _NP_SCORER_CACHE = (npscorer, fscore)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "RDKit NP scorer not available (%s); np_likeness will be left blank.",
            exc,
        )
        _NP_SCORER_CACHE = (None, None)

    return _NP_SCORER_CACHE


def np_likeness(smiles: str) -> str:
    """Compute RDKit NP-likeness score for a SMILES string. Returns "" on failure."""
    npscorer_mod, fscore = _load_np_scorer()
    if npscorer_mod is None or fscore is None:
        return ""

    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return ""
        score = npscorer_mod.scoreMol(mol, fscore)
        return _s(round(score, 4))
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# PAINS filter
# ---------------------------------------------------------------------------

_PAINS_CATALOG_CACHE: Optional[Any] = None
_PAINS_CATALOG_LOADED = False


def _load_pains_catalog() -> Optional[Any]:
    """Load the RDKit PAINS filter catalog. Returns catalog or None if unavailable."""
    global _PAINS_CATALOG_CACHE, _PAINS_CATALOG_LOADED
    if _PAINS_CATALOG_LOADED:
        return _PAINS_CATALOG_CACHE

    _PAINS_CATALOG_LOADED = True
    try:
        from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

        params = FilterCatalogParams()
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
        catalog = FilterCatalog(params)
        log.info("RDKit PAINS catalog loaded (%d entries)", catalog.GetNumEntries())
        _PAINS_CATALOG_CACHE = catalog
    except Exception as exc:  # noqa: BLE001
        log.warning("PAINS catalog unavailable (%s); check_pains will return False.", exc)
        _PAINS_CATALOG_CACHE = None

    return _PAINS_CATALOG_CACHE


def check_pains(smiles: str) -> bool:
    """Check if SMILES matches a PAINS pattern.

    Returns True (PAINS-positive) or False (clean or unresolvable — catalog
    unavailable, unparseable SMILES).
    Note: PAINS flags assay interference compounds (Baell & Holloway, J. Med.
    Chem. 2010). Used for reporting only — not a hard filter in this
    computational pipeline.
    """
    catalog = _load_pains_catalog()
    if catalog is None:
        return False

    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False
        return bool(catalog.HasMatch(mol))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# ChEMBL by-InChIKey lookup
# ---------------------------------------------------------------------------


def http_cache_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.json"


def _chembl_molecule_properties(payload: Dict[str, Any]) -> Dict[str, str]:
    props = payload.get("molecule_properties") or {}
    if not isinstance(props, dict):
        props = {}
    return {
        "qed_score": _s(props.get("qed_weighted")),
        "np_likeness_score": _s(props.get("np_likeness_score")),
        "num_ro5_violations": _s(props.get("num_ro5_violations")),
    }


def chembl_detail_by_inchikey(inchi_key: str, cache_dir: Path) -> Dict[str, str]:
    """Fetch ChEMBL molecule properties for a single InChIKey.

    Queries ChEMBL's /molecule search endpoint filtered by
    molecule_structures__standard_inchi_key (confirmed live to return the
    exact matching molecule; unlike /activity's InChIKey filter, which is a
    silent no-op, this filter genuinely restricts by structure).

    Returns {qed_score, np_likeness_score, num_ro5_violations}, blank values
    on a miss or fetch failure. Disk-cached via the same http_cache_path
    convention as the 04_enrich HTTP cache, so repeated lookups (including
    across runs) cost zero additional API calls.
    """
    blank = {"qed_score": "", "np_likeness_score": "", "num_ro5_violations": ""}

    inchi_key = (inchi_key or "").strip()
    if not inchi_key:
        return blank

    url = (
        f"{CHEMBL_BASE_URL}/molecule"
        f"?molecule_structures__standard_inchi_key={quote(inchi_key, safe='')}"
        f"&format=json"
    )
    cache_path = http_cache_path(cache_dir, url)

    data: Optional[Dict[str, Any]] = None
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = None

    if data is None:
        try:
            import requests  # available in ETL venv

            resp = requests.get(
                url,
                headers={"Accept": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as exc:  # noqa: BLE001
            log.warning("ChEMBL by-InChIKey fetch failed %s: %s", inchi_key, exc)
            return blank

    molecules = (data or {}).get("molecules") or []
    if not molecules:
        return blank

    return _chembl_molecule_properties(molecules[0])
