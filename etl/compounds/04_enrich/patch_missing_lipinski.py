"""patch_missing_lipinski.py

Run AFTER 04_enrich/run.py and patch_missing_smiles.py, BEFORE 05_build_canonical/run.py.

Two-pass Lipinski/ADME descriptor recovery for compounds where `logp` is empty:

  Pass 1 (ChEMBL API) — rows with a known `chembl_id`: fetches the ChEMBL molecule
                         detail endpoint and extracts molecule_properties. Checks the
                         existing HTTP cache first so previously fetched responses cost
                         zero API calls.
  Pass 2 (RDKit)      — rows still missing after Pass 1 that have a non-empty `smiles`:
                         computes MolLogP, NumHBD, NumHBA, TPSA, NumRotatableBonds
                         locally from the SMILES string. qed_score is not computed
                         (requires QED module); np_likeness_score handled in Pass 2b.

  Pass 2b (RDKit NP)  — all rows where np_likeness_score is still null but smiles is
                         present (covers both rdkit_computed and any chembl_api rows that
                         returned an empty np_likeness_score). Uses the RDKit NP scorer
                         from RDKit Contrib (NP_Score/npscorer.py). Degrades gracefully
                         if the NP scorer module is unavailable.

Sets `lipinski_source` on each patched row:
  chembl_api           — properties from ChEMBL molecule_properties
  rdkit_computed       — Lipinski properties computed from SMILES via RDKit
  rdkit_computed+rdkit_np — Lipinski + NP-likeness both computed via RDKit
  chembl_api+rdkit_np  — ChEMBL Lipinski + RDKit NP-likeness (ChEMBL returned empty NP)
  rdkit_np             — only NP-likeness added (Lipinski already present from elsewhere)
  (empty string)       — compound remains unresolved (no chembl_id, no usable SMILES)

Usage:
    python patch_missing_lipinski.py [--enrich-out PATH] [--dry-run] [--no-rdkit]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("patch_lipinski")

CHEMBL_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
REQUEST_DELAY = 0.35
REQUEST_TIMEOUT = 30

LIPINSKI_FIELDS = (
    "tpsa",
    "logp",
    "hbond_donors",
    "hbond_acceptors",
    "rotatable_bonds",
    "qed_score",
    "np_likeness_score",
    "num_ro5_violations",
)


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# ChEMBL helpers  (logic mirrored from 04_enrich/run.py chembl_properties())
# ---------------------------------------------------------------------------


def _s(val: Any) -> str:
    if val is None or val == "":
        return ""
    return str(val).strip()


def chembl_properties(payload: Dict[str, Any]) -> Dict[str, str]:
    props = payload.get("molecule_properties") or {}
    if not isinstance(props, dict):
        props = {}
    return {
        "tpsa": _s(props.get("psa")),
        "logp": _s(props.get("alogp")),
        "hbond_donors": _s(props.get("hbd")),
        "hbond_acceptors": _s(props.get("hba")),
        "rotatable_bonds": _s(props.get("rtb")),
        "qed_score": _s(props.get("qed_weighted")),
        "np_likeness_score": _s(props.get("np_likeness_score")),
        "num_ro5_violations": _s(props.get("num_ro5_violations")),
    }


def http_cache_path(chembl_cache_dir: Path, url: str) -> Path:
    return chembl_cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.json"


def fetch_chembl_molecule(
    chembl_id: str,
    chembl_cache_dir: Path,
) -> Optional[Dict[str, Any]]:
    """Return ChEMBL molecule detail JSON from cache or live API."""
    url = f"{CHEMBL_BASE_URL}/molecule/{quote(chembl_id, safe='')}.json"
    cache_path = http_cache_path(chembl_cache_dir, url)

    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                return json.load(f), True  # type: ignore[return-value]
        except (json.JSONDecodeError, OSError):
            pass

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
        return data, False  # type: ignore[return-value]
    except Exception as exc:  # noqa: BLE001
        log.warning("ChEMBL fetch failed %s: %s", chembl_id, exc)
        return None, False  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# RDKit helpers
# ---------------------------------------------------------------------------


def _load_np_scorer():
    """Load the RDKit NP scorer model. Returns the fscore object or None if unavailable."""
    try:
        from rdkit.Chem import RDConfig
        import os
        import sys
        sys.path.append(os.path.join(RDConfig.RDContribDir, "NP_Score"))
        import npscorer  # type: ignore[import]
        fscore = npscorer.readNPModel()
        log.info("RDKit NP scorer loaded from %s", os.path.join(RDConfig.RDContribDir, "NP_Score"))
        return npscorer, fscore
    except Exception as exc:
        log.warning("RDKit NP scorer not available (%s); np_likeness_score will be left blank for rdkit_computed compounds.", exc)
        return None, None


def rdkit_properties(smiles: str) -> Optional[Dict[str, str]]:
    """Compute Lipinski descriptors from SMILES using RDKit. Returns None on failure."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
    except ImportError:
        log.warning("RDKit not importable — skipping RDKit pass.")
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
        # qed_score and np_likeness_score handled separately; leave blank here
        "qed_score": "",
        "np_likeness_score": "",
        "num_ro5_violations": "",
    }


def compute_np_score(smiles: str, npscorer_mod: Any, fscore: Any) -> str:
    """Compute RDKit NP-likeness score for a SMILES string. Returns empty string on failure."""
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return ""
        score = npscorer_mod.scoreMol(mol, fscore)
        return _s(round(score, 4))
    except Exception:
        return ""


def _load_pains_catalog() -> Optional[Any]:
    """Load the RDKit PAINS filter catalog. Returns catalog or None if unavailable."""
    try:
        from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams
        params = FilterCatalogParams()
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
        catalog = FilterCatalog(params)
        log.info("RDKit PAINS catalog loaded (%d entries)", catalog.GetNumEntries())
        return catalog
    except Exception as exc:
        log.warning("PAINS catalog unavailable (%s); is_pains_positive will be left empty.", exc)
        return None


def check_pains(smiles: str, catalog: Any) -> str:
    """Check if SMILES matches a PAINS pattern.

    Returns 'true' (PAINS-positive), 'false' (clean), or '' on parse failure.
    Note: PAINS flags assay interference compounds (Baell & Holloway, J. Med. Chem. 2010).
    Used for reporting only — not a hard filter in this computational pipeline.
    """
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return ""
        return "true" if catalog.HasMatch(mol) else "false"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def is_missing(row: Dict[str, str]) -> bool:
    return (row.get("logp") or "").strip() == ""


def apply_props(row: Dict[str, str], props: Dict[str, str], source: str) -> None:
    for field, value in props.items():
        if value:
            row[field] = value
    row["lipinski_source"] = source


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch missing Lipinski/ADME descriptors in compound enrichment results."
    )
    parser.add_argument(
        "--enrich-out",
        default=str(Path(__file__).resolve().parent / "out"),
        help="Path to 04_enrich/out/ directory (default: ./out).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen without writing anything.",
    )
    parser.add_argument(
        "--no-rdkit",
        action="store_true",
        help="Skip RDKit pass (ChEMBL API only).",
    )
    args = parser.parse_args()

    enrich_out = Path(args.enrich_out).resolve()
    results_csv = enrich_out / "compound_enrichment_results.csv"
    chembl_cache_dir = enrich_out / "cache" / "http" / "chembl"

    if not results_csv.exists():
        raise SystemExit(f"Not found: {results_csv}")

    log.info("Enrich output dir : %s", enrich_out)
    log.info("Dry run           : %s", args.dry_run)
    log.info("RDKit pass        : %s", not args.no_rdkit)

    results = load_csv(results_csv)
    if not results:
        log.info("No rows found in results CSV.")
        return 0

    result_fields = list(results[0].keys())
    if "lipinski_source" not in result_fields:
        result_fields.append("lipinski_source")
    if "is_pains_positive" not in result_fields:
        result_fields.append("is_pains_positive")

    for row in results:
        row.setdefault("lipinski_source", "")
        row.setdefault("is_pains_positive", "")

    missing = [r for r in results if is_missing(r)]
    log.info("Rows missing logp : %d / %d", len(missing), len(results))

    if not missing:
        log.info("Nothing to patch.")
        return 0

    # --- Pass 1: ChEMBL API ---
    chembl_patched = 0
    still_missing: List[Dict[str, str]] = []

    for row in missing:
        chembl_id = (row.get("chembl_id") or "").strip()
        if not chembl_id:
            still_missing.append(row)
            continue

        payload, from_cache = fetch_chembl_molecule(chembl_id, chembl_cache_dir)
        if payload:
            props = chembl_properties(payload)
            has_data = any(v for v in props.values())
            if has_data:
                log.info(
                    "ChEMBL  %-20s  logp=%-6s tpsa=%-6s  [%s]",
                    chembl_id,
                    props.get("logp", ""),
                    props.get("tpsa", ""),
                    "cache" if from_cache else "live",
                )
                if not args.dry_run:
                    apply_props(row, props, "chembl_api")
                chembl_patched += 1
                if not from_cache:
                    time.sleep(REQUEST_DELAY)
                continue

        still_missing.append(row)

    # --- Pass 2: RDKit (Lipinski descriptors) ---
    rdkit_patched = 0
    unresolved = 0

    # Load NP scorer once before the loop (may be None if unavailable)
    np_scorer_mod, np_fscore = (None, None)
    if not args.no_rdkit:
        np_scorer_mod, np_fscore = _load_np_scorer()

    if not args.no_rdkit:
        for row in still_missing:
            smiles = (row.get("smiles") or "").strip()
            if not smiles:
                unresolved += 1
                continue

            props = rdkit_properties(smiles)
            if props:
                log.info(
                    "RDKit   %-40s  logp=%-6s tpsa=%s",
                    smiles[:40],
                    props.get("logp", ""),
                    props.get("tpsa", ""),
                )
                if not args.dry_run:
                    apply_props(row, props, "rdkit_computed")
                rdkit_patched += 1
            else:
                unresolved += 1
    else:
        unresolved = len(still_missing)

    # --- Pass 2b: RDKit NP-likeness score ---
    # Applied to all rows where np_likeness_score is still null but smiles is present,
    # including both rdkit_computed rows from Pass 2 and any chembl_api rows that came
    # back with an empty np_likeness_score.
    np_patched = 0
    if not args.no_rdkit and np_scorer_mod is not None and np_fscore is not None:
        for row in results:
            if (row.get("np_likeness_score") or "").strip():
                continue  # already has a value
            smiles = (row.get("smiles") or "").strip()
            if not smiles:
                continue
            score = compute_np_score(smiles, np_scorer_mod, np_fscore)
            if score:
                if not args.dry_run:
                    row["np_likeness_score"] = score
                    # Append +rdkit_np to lipinski_source to indicate provenance
                    existing_source = (row.get("lipinski_source") or "").strip()
                    if existing_source and "+rdkit_np" not in existing_source:
                        row["lipinski_source"] = existing_source + "+rdkit_np"
                    elif not existing_source:
                        row["lipinski_source"] = "rdkit_np"
                np_patched += 1
        log.info("NP-likeness (RDKit NP scorer)  : %d computed", np_patched)
    elif not args.no_rdkit:
        log.warning("[patch] NP scorer unavailable; np_likeness_score left null for rdkit_computed compounds")

    # --- Pass 3: PAINS flag ---
    # Flags compounds matching PAINS patterns (Baell & Holloway, J. Med. Chem. 53:2719-2740, 2010).
    # Reporting only — not a filter. Compounds with no SMILES get an empty string (unknown).
    pains_catalog = None
    if not args.no_rdkit:
        pains_catalog = _load_pains_catalog()

    pains_positive = 0
    pains_computed = 0
    if pains_catalog is not None:
        for row in results:
            smiles = (row.get("smiles") or "").strip()
            if not smiles:
                continue
            flag = check_pains(smiles, pains_catalog)
            row["is_pains_positive"] = flag
            if flag:
                pains_computed += 1
            if flag == "true":
                pains_positive += 1
        log.info("PAINS flags computed          : %d positive / %d total", pains_positive, pains_computed)

    # --- Write ---
    if not args.dry_run and (chembl_patched + rdkit_patched + np_patched + pains_computed) > 0:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = enrich_out / f"backup_pre_patch_lipinski_{ts}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(results_csv, backup_dir / results_csv.name)
        log.info("Backed up original to %s", backup_dir)

        write_csv(results_csv, results, result_fields)
        log.info("Patched CSV written.")

    # --- Summary ---
    log.info("─" * 60)
    log.info("Total missing logp            : %d", len(missing))
    log.info("Patched via ChEMBL API        : %d", chembl_patched)
    log.info("Patched via RDKit             : %d", rdkit_patched)
    log.info("Unresolved (no hit / SMILES)  : %d", unresolved)
    log.info("NP-likeness computed (RDKit)  : %d", np_patched)
    log.info("PAINS positive (flagged)      : %d / %d", pains_positive, pains_computed)
    log.info("─" * 60)

    if args.dry_run:
        log.info("DRY RUN — nothing written.")
    else:
        remaining = len([r for r in results if is_missing(r)])
        log.info("Rows still missing logp : %d", remaining)
        if remaining == 0:
            log.info("All descriptors filled. Run 05_build_canonical next.")
        else:
            log.info("Some compounds unresolvable. Proceed to 05_build_canonical.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
