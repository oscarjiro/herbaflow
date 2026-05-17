"""patch_missing_smiles.py

Run this BEFORE re-running 04_enrich.py when you only care about filling in
missing SMILES.

What it does (in order):
  1. FREE PASS  — reads each missing-SMILES candidate's existing cache JSON and
                  checks ordered_hits for any hit that already has a SMILES.
                  If found, patches the result CSV directly (zero API calls).
  2. INVALIDATE — for candidates still missing SMILES after step 1, deletes
                  only the candidate-level cache file so 04_enrich will
                  re-process them. The HTTP cache (PubChem/ChEMBL raw responses)
                  is left untouched, so old lookups are replayed for free.

After running this, re-run 04_enrich.py normally.
Candidates that already had SMILES are served from candidate cache instantly.
Only the invalidated ones hit the enrichment logic again.

Usage:
    python patch_missing_smiles.py [--settings path/to/settings.yml] [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("patch_smiles")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def best_smiles_from_cache(cache_data: Dict[str, Any]) -> str:
    """
    Walk ordered_hits in the candidate cache and return the first non-empty
    SMILES found. This catches cases where a hit had SMILES but wasn't
    selected as best (scoring edge cases, cross-source tie-breaking, etc.).
    """
    for hit in cache_data.get("ordered_hits", []):
        smiles = (hit.get("smiles") or "").strip()
        if smiles:
            return smiles
    return ""


def resolve_settings_paths(settings_path: Path):
    """Minimal settings parse — just enough to find the output directories."""
    try:
        import yaml
    except ImportError:
        raise SystemExit("PyYAML required: pip install pyyaml")

    with settings_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    project_root = (settings_path.parent / cfg["project"]["project_root"]).resolve()
    paths = cfg.get("paths", {})
    step_dirs = paths.get("step_dirs", {})

    enrich_out = (
        project_root / step_dirs.get("enrich_out", "compounds/04_enrich/out")
    ).resolve()
    return enrich_out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch missing SMILES from enrichment cache."
    )
    parser.add_argument(
        "--settings",
        default=str(Path(__file__).resolve().parents[1] / "settings.yml"),
        help="Path to settings.yml (auto-detected if omitted).",
    )
    parser.add_argument(
        "--enrich-out",
        default=str(Path(__file__).resolve().parents[0] / "out"),
        help="Direct path to 04_enrich/out/ directory (alternative to --settings).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen without writing anything.",
    )
    args = parser.parse_args()

    # --- Resolve output directory ---
    if args.enrich_out:
        enrich_out = Path(args.enrich_out).resolve()
    elif args.settings:
        enrich_out = resolve_settings_paths(Path(args.settings).resolve())
    else:
        # Try common relative locations
        for candidate in [
            Path("compounds/04_enrich/out"),
            Path("../compounds/04_enrich/out"),
            Path("04_enrich/out"),
        ]:
            if candidate.exists():
                enrich_out = candidate.resolve()
                break
        else:
            raise SystemExit(
                "Could not auto-detect enrich output directory. "
                "Pass --enrich-out or --settings."
            )

    results_csv = enrich_out / "compound_enrichment_results.csv"
    cache_idx_csv = enrich_out / "compound_enrichment_cache.csv"
    member_map_csv = enrich_out / "compound_enrichment_member_map.csv"

    for p in (results_csv, cache_idx_csv):
        if not p.exists():
            raise SystemExit(f"Required file not found: {p}")

    log.info("Enrich output dir : %s", enrich_out)
    log.info("Dry run           : %s", args.dry_run)

    # --- Load data ---
    results = load_csv(results_csv)
    cache_index = load_csv(cache_idx_csv)
    member_map = load_csv(member_map_csv) if member_map_csv.exists() else []

    # Build lookup: cache_key -> cache_file path
    cache_file_by_key: Dict[str, Path] = {}
    for row in cache_index:
        key = row.get("cache_key", "").strip()
        file = row.get("cache_file", "").strip()
        if key and file:
            cache_file_by_key[key] = Path(file)

    # --- Step 1: FREE PASS — patch from existing cache ordered_hits ---
    result_fields = list(results[0].keys()) if results else []
    patched_free = 0
    still_missing: List[Dict[str, str]] = []

    for row in results:
        smiles = (row.get("smiles") or "").strip()
        if smiles:
            continue  # already has SMILES, nothing to do

        cache_key = (row.get("cache_key") or "").strip()
        cache_file = cache_file_by_key.get(cache_key)

        recovered = ""
        if cache_file:
            cache_data = load_json(cache_file)
            if cache_data:
                recovered = best_smiles_from_cache(cache_data)

        if recovered:
            log.info(
                "FREE PASS  %s → SMILES recovered from ordered_hits: %.40s…",
                row.get("compound_candidate_id", "?"),
                recovered,
            )
            if not args.dry_run:
                row["smiles"] = recovered
                # Also patch member_map rows for this candidate
                cid = row.get("compound_candidate_id", "")
                for mrow in member_map:
                    if mrow.get("compound_candidate_id") == cid:
                        mrow["chosen_smiles"] = recovered
            patched_free += 1
        else:
            still_missing.append(row)

    # --- Step 2: INVALIDATE candidate caches for rows still missing ---
    invalidated = 0
    no_cache_found = 0

    for row in still_missing:
        cache_key = (row.get("cache_key") or "").strip()
        cache_file = cache_file_by_key.get(cache_key)

        if not cache_file or not cache_file.exists():
            log.debug(
                "No candidate cache for %s (will be processed fresh on re-run).",
                row.get("compound_candidate_id", "?"),
            )
            no_cache_found += 1
            continue

        log.info(
            "INVALIDATE %s → deleting %s",
            row.get("compound_candidate_id", "?"),
            cache_file.name,
        )
        if not args.dry_run:
            cache_file.unlink(missing_ok=True)
        invalidated += 1

    # --- Write patched CSVs ---
    if not args.dry_run and patched_free > 0:
        # Back up originals
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = enrich_out / f"backup_pre_patch_{ts}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(results_csv, backup_dir / results_csv.name)
        shutil.copy2(cache_idx_csv, backup_dir / cache_idx_csv.name)
        if member_map_csv.exists():
            shutil.copy2(member_map_csv, backup_dir / member_map_csv.name)
        log.info("Backed up originals to %s", backup_dir)

        write_csv(results_csv, results, result_fields)
        if member_map:
            member_fields = list(member_map[0].keys())
            write_csv(member_map_csv, member_map, member_fields)
        log.info("Patched CSVs written.")

    # --- Summary ---
    total_missing = len(still_missing) + patched_free
    log.info("─" * 60)
    log.info("Total rows missing SMILES     : %d", total_missing)
    log.info(
        "Patched from existing cache   : %d  (free, no re-run needed)", patched_free
    )
    log.info(
        "Candidate caches invalidated  : %d  (will re-process on re-run)", invalidated
    )
    log.info(
        "No cache file found           : %d  (will be treated as new on re-run)",
        no_cache_found,
    )
    log.info("─" * 60)

    if args.dry_run:
        log.info("DRY RUN — nothing was written or deleted.")
    elif invalidated > 0 or no_cache_found > 0:
        log.info(
            "Next step: re-run 04_enrich.py  — only %d candidates will be re-processed.",
            invalidated + no_cache_found,
        )
        log.info(
            "All %d candidates that already had SMILES are served from candidate cache instantly.",
            len(results) - total_missing,
        )
    else:
        log.info(
            "Nothing left to invalidate. All missing SMILES were patched in-place."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
