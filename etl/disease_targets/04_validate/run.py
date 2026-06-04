"""
04_validate/run.py — Validate canonical disease-target outputs.

Checks:
  - Required columns present in all three tables
  - No orphan disease_targets (target_id and disease_id must resolve)
  - All 10 diseases have at least one target association
  - No duplicate (disease_id, target_id) pairs
  - Score range valid (≥ threshold, ≤ 1.0)
  - target_aliases: all target_id values exist in targets.csv
  - UniProt coverage (warn if below threshold)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from disease_targets.utils import read_frame
from shared.utils import (
    ETL_ROOT,
    ensure_dir,
    load_settings,
    make_run_id,
    now_iso,
    setup_logging,
    write_json,
)

TARGETS_REQUIRED = [
    "target_id", "canonical_key", "gene_symbol", "protein_name",
    "uniprot_accession", "source_name", "retrieved_at",
]
ALIASES_REQUIRED = [
    "target_alias_id", "target_id", "alias_name", "alias_key", "alias_type",
    "retrieved_at",
]
DT_REQUIRED = [
    "disease_target_id", "disease_id", "target_id", "source_name",
    "association_type", "score", "retrieved_at",
]


def _check(name: str, ok: bool, detail: str = "") -> dict:
    status = "PASS" if ok else "FAIL"
    return {"check": name, "status": status, "detail": detail}


def _warn(name: str, ok: bool, detail: str = "") -> dict:
    status = "PASS" if ok else "WARN"
    return {"check": name, "status": status, "detail": detail}


def run(cfg: dict, canonical_dir: Path, diseases_csv: Path, output_dir: Path) -> int:
    log = setup_logging("disease_targets.04_validate", cfg)
    ensure_dir(output_dir)

    min_score = float(cfg["filtering"]["min_association_score"])
    warn_threshold = float(cfg["filtering"]["uniprot_coverage_warn_threshold"])
    fail_on: list[str] = cfg.get("validation", {}).get("fail_on", [])

    targets_df = read_frame(canonical_dir / "targets.csv")
    aliases_df = read_frame(canonical_dir / "target_aliases.csv")
    dt_df      = read_frame(canonical_dir / "disease_targets.csv")
    diseases_df = read_frame(diseases_csv)

    results: list[dict] = []
    has_fail = False

    # ------------------------------------------------------------------
    # Column presence
    # ------------------------------------------------------------------
    for table, df, required in [
        ("targets", targets_df, TARGETS_REQUIRED),
        ("target_aliases", aliases_df, ALIASES_REQUIRED),
        ("disease_targets", dt_df, DT_REQUIRED),
    ]:
        missing = [c for c in required if c not in df.columns]
        ok = len(missing) == 0
        results.append(_check(f"{table}_required_columns", ok, f"missing: {missing}" if missing else ""))
        if not ok:
            has_fail = True

    # ------------------------------------------------------------------
    # No empty primary keys
    # ------------------------------------------------------------------
    for table, df, pk in [
        ("targets", targets_df, "target_id"),
        ("target_aliases", aliases_df, "target_alias_id"),
        ("disease_targets", dt_df, "disease_target_id"),
    ]:
        empty = df[pk].str.strip().eq("").sum() if pk in df.columns else 0
        ok = empty == 0
        results.append(_check(f"{table}_no_empty_pk", ok, f"{empty} empty PKs" if not ok else ""))
        if not ok:
            has_fail = True

    # ------------------------------------------------------------------
    # Orphan checks
    # ------------------------------------------------------------------
    if "target_id" in dt_df.columns and "target_id" in targets_df.columns:
        valid_tids = set(targets_df["target_id"])
        orphan_targets = ~dt_df["target_id"].isin(valid_tids)
        ok = orphan_targets.sum() == 0
        results.append(_check("disease_targets_no_orphan_targets", ok,
                               f"{orphan_targets.sum()} orphan target_ids" if not ok else ""))
        if not ok:
            has_fail = True

    if "disease_id" in dt_df.columns and "disease_id" in diseases_df.columns:
        valid_dids = set(diseases_df["disease_id"])
        orphan_diseases = ~dt_df["disease_id"].isin(valid_dids)
        ok = orphan_diseases.sum() == 0
        results.append(_check("disease_targets_no_orphan_diseases", ok,
                               f"{orphan_diseases.sum()} unknown disease_ids" if not ok else ""))
        if not ok:
            has_fail = True

    if "target_id" in aliases_df.columns and "target_id" in targets_df.columns:
        valid_tids = set(targets_df["target_id"])
        orphan_alias = ~aliases_df["target_id"].isin(valid_tids)
        ok = orphan_alias.sum() == 0
        results.append(_check("target_aliases_no_orphans", ok,
                               f"{orphan_alias.sum()} orphan target_ids in aliases" if not ok else ""))
        if not ok:
            has_fail = True

    # ------------------------------------------------------------------
    # All 10 diseases covered
    # ------------------------------------------------------------------
    if "disease_id" in dt_df.columns and "disease_id" in diseases_df.columns:
        disease_ids_in_output = set(dt_df["disease_id"])
        all_disease_ids = set(diseases_df["disease_id"])
        uncovered = all_disease_ids - disease_ids_in_output
        ok = len(uncovered) == 0
        results.append(_check("all_diseases_covered", ok,
                               f"uncovered: {uncovered}" if not ok else f"all {len(all_disease_ids)} covered"))
        if not ok:
            has_fail = True

    # ------------------------------------------------------------------
    # No duplicate (disease_id, target_id)
    # ------------------------------------------------------------------
    if "disease_id" in dt_df.columns and "target_id" in dt_df.columns:
        dupes = dt_df.duplicated(subset=["disease_id", "target_id"]).sum()
        ok = dupes == 0
        results.append(_check("disease_targets_no_dupes", ok, f"{dupes} duplicate pairs" if not ok else ""))
        if not ok:
            has_fail = True

    # ------------------------------------------------------------------
    # Score range
    # ------------------------------------------------------------------
    if "score" in dt_df.columns:
        dt_df["_score"] = dt_df["score"].astype(float)
        below = (dt_df["_score"] < min_score).sum()
        above = (dt_df["_score"] > 1.0).sum()
        ok = below == 0 and above == 0
        results.append(_check("score_range_valid", ok,
                               f"{below} below threshold, {above} above 1.0" if not ok else
                               f"range [{dt_df['_score'].min():.3f}, {dt_df['_score'].max():.3f}]"))
        if not ok:
            has_fail = True

    # ------------------------------------------------------------------
    # UniProt coverage (warn only)
    # ------------------------------------------------------------------
    if "uniprot_accession" in targets_df.columns:
        with_uniprot = targets_df["uniprot_accession"].str.strip().ne("").sum()
        coverage = with_uniprot / len(targets_df) if len(targets_df) else 0
        ok = coverage >= warn_threshold
        result = _warn("uniprot_coverage", ok,
                        f"{coverage:.1%} (threshold: {warn_threshold:.0%})")
        result["uniprot_coverage"] = round(float(coverage), 4)
        results.append(result)
        if not ok:
            log.warning("UniProt coverage %.1f%% below warn threshold %.1f%%",
                         coverage * 100, warn_threshold * 100)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    fails  = [r for r in results if r["status"] == "FAIL"]
    warns  = [r for r in results if r["status"] == "WARN"]
    passes = [r for r in results if r["status"] == "PASS"]

    report = {
        "run_id":    make_run_id("validate"),
        "validated_at": now_iso(),
        "summary": {
            "pass": len(passes),
            "warn": len(warns),
            "fail": len(fails),
        },
        "counts": {
            "targets":         len(targets_df),
            "target_aliases":  len(aliases_df),
            "disease_targets": len(dt_df),
            "diseases_covered": dt_df["disease_id"].nunique() if "disease_id" in dt_df.columns else 0,
        },
        "checks": results,
    }
    write_json(report, output_dir / "validation_report.json")

    for r in results:
        level = log.error if r["status"] == "FAIL" else (log.warning if r["status"] == "WARN" else log.info)
        level("[%s] %s %s", r["status"], r["check"], r.get("detail", ""))

    log.info("Validation complete: %d pass, %d warn, %d fail", len(passes), len(warns), len(fails))

    # Fail if any FAIL checks exist, or if fail_on warn checks triggered
    if has_fail:
        return 1
    if "low_uniprot_coverage" in fail_on:
        low_cov = [r for r in results if r["check"] == "uniprot_coverage" and r["status"] == "WARN"]
        if low_cov:
            return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate disease-target canonical outputs")
    parser.add_argument("--canonical-dir", type=Path)
    parser.add_argument("--diseases-csv",  type=Path)
    parser.add_argument("--output-dir",    type=Path)
    args = parser.parse_args()

    cfg   = load_settings("disease_targets")
    paths = cfg["paths"]

    canonical_dir = Path(args.canonical_dir) if args.canonical_dir else ETL_ROOT / paths["canonical_out"]
    diseases_csv  = Path(args.diseases_csv)  if args.diseases_csv  else ETL_ROOT / paths["diseases_input"]
    output_dir    = Path(args.output_dir)    if args.output_dir    else ETL_ROOT / paths["validate_out"]

    sys.exit(run(cfg, canonical_dir, diseases_csv, output_dir))
