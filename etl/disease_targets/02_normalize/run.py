"""
02_normalize/run.py — Normalize and deduplicate targets from raw associations.

Reads raw_associations.csv, applies text normalization, computes canonical_key
per target, deduplicates, and writes:
  - targets_raw.csv        (one row per unique target)
  - disease_targets_raw.csv (one row per disease x target pair, max score)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging, ensure_dir, now_iso, make_run_id, write_json
from disease_targets.utils import (
    read_csv, write_csv, normalize_text, safe_str, validate_required_columns,
    canonical_key_for_target,
)

REQUIRED_INPUT_COLS = [
    "disease_key", "disease_id", "ensembl_id", "gene_symbol",
    "approved_name", "uniprot_accession", "association_score",
]


def run(cfg: dict, input_dir: Path, output_dir: Path) -> int:
    log = setup_logging("disease_targets.02_normalize", cfg)
    ensure_dir(output_dir)

    raw_csv = input_dir / "raw_associations.csv"
    if not raw_csv.exists():
        log.error("Input not found: %s", raw_csv)
        return 1

    df = read_csv(raw_csv)
    log.info("Loaded %d rows from raw_associations.csv", len(df))
    validate_required_columns(df, REQUIRED_INPUT_COLS, table_name="raw_associations")

    min_score = float(cfg["filtering"]["min_association_score"])

    # Normalize text fields
    df["gene_symbol"]       = df["gene_symbol"].str.strip().str.upper()
    df["approved_name"]     = df["approved_name"].apply(normalize_text)
    df["uniprot_accession"] = df["uniprot_accession"].str.strip().str.upper()
    df["ensembl_id"]        = df["ensembl_id"].str.strip()

    # Re-apply score filter defensively (cache may have old threshold data)
    df["association_score"] = df["association_score"].astype(float)
    before = len(df)
    df = df[df["association_score"] >= min_score].copy()
    if len(df) < before:
        log.info("Filtered %d rows below score threshold %.2f", before - len(df), min_score)

    # Compute canonical_key
    df["canonical_key"] = df.apply(
        lambda r: canonical_key_for_target(r["uniprot_accession"], r["ensembl_id"]),
        axis=1,
    )

    # ---------------------------------------------------------------------------
    # targets_raw: one row per unique target
    # Sort by ensembl_id for determinism, then dedup by canonical_key
    # ---------------------------------------------------------------------------
    target_cols = ["canonical_key", "ensembl_id", "gene_symbol", "approved_name",
                   "uniprot_accession", "uniprot_source"]
    targets_df = (
        df[target_cols]
        .sort_values("ensembl_id")
        .drop_duplicates(subset=["canonical_key"], keep="first")
        .copy()
    )
    targets_df["organism_tax_id"] = str(cfg["filtering"]["organism_tax_id"])

    write_csv(targets_df, output_dir / "targets_raw.csv")
    log.info("targets_raw.csv: %d unique targets", len(targets_df))

    # ---------------------------------------------------------------------------
    # disease_targets_raw: one row per (disease_id, canonical_key), max score
    # ---------------------------------------------------------------------------
    dt_df = (
        df.groupby(["disease_id", "disease_key", "canonical_key"], as_index=False)
        ["association_score"]
        .max()
    )
    dt_df["association_score"] = dt_df["association_score"].astype(str)
    dt_df["retrieved_at"] = now_iso()

    write_csv(dt_df, output_dir / "disease_targets_raw.csv")
    log.info("disease_targets_raw.csv: %d pairs", len(dt_df))

    # UniProt coverage stat
    with_uniprot = targets_df["uniprot_accession"].str.strip().ne("").sum()
    coverage = with_uniprot / len(targets_df) if len(targets_df) else 0

    write_json(
        {
            "run_id":              make_run_id("normalize"),
            "input_rows":          before,
            "filtered_rows":       len(df),
            "unique_targets":      len(targets_df),
            "disease_target_pairs": len(dt_df),
            "uniprot_coverage":    round(coverage, 4),
        },
        output_dir / "run_manifest.json",
    )

    warn_threshold = float(cfg["filtering"]["uniprot_coverage_warn_threshold"])
    if coverage < warn_threshold:
        log.warning(
            "UniProt coverage %.1f%% is below warn threshold %.1f%%",
            coverage * 100, warn_threshold * 100,
        )
    else:
        log.info("UniProt coverage: %.1f%%", coverage * 100)

    log.info("Normalize complete.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalize disease-target associations")
    parser.add_argument("--input-dir",  type=Path, help="Directory containing raw_associations.csv")
    parser.add_argument("--output-dir", type=Path, help="Output directory")
    args = parser.parse_args()

    cfg = load_settings("disease_targets")
    paths = cfg["paths"]

    input_dir  = Path(args.input_dir)  if args.input_dir  else ETL_ROOT / paths["fetch_out"]
    output_dir = Path(args.output_dir) if args.output_dir else ETL_ROOT / paths["normalize_out"]

    sys.exit(run(cfg, input_dir, output_dir))
