"""
01_extract: Stage raw plant scrape output into a clean, deduplicated CSV.

Reads raw KNApSAcK plant scrape data from ~/knapsack/out/plants.csv and writes a
staging file to 01_extract/out/stg_plants.csv.

What this script does:
- Preserves each raw row structure
- Trims obvious outer whitespace only
- Adds source_batch_id if missing, or fills blanks with the provided batch id
- Adds raw_hash as a stable hash of the row contents
- Drops rows that are missing a detail_url (no source page to canonicalize)
- Removes exact duplicate rows
- Writes a small extraction log into the same output folder

What this script does not do:
- No taxonomy normalization
- No GBIF matching
- No canonicalization of plant names
- No semantic cleaning beyond outer whitespace trimming

Example:
    python extract_plants.py \
        --input ../knapsack/out/plants.csv \
        --output-dir 01_extract/out \
        --source-batch-id knapsack_world_id_2026_04_17
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
import argparse
import csv
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from shared.utils import ETL_ROOT, ensure_dir, load_settings
from shared.utils import setup_logging as shared_setup_logging


def _defaults() -> tuple[Path, Path, str, str]:
    cfg = load_settings("plants")
    step = cfg["paths"]["extract"]
    return (
        ETL_ROOT / step["input"],
        ETL_ROOT / step["output_dir"],
        step["output_file"],
        step["log_file"],
    )


@dataclass(frozen=True)
class ExtractResult:
    input_rows: int
    output_rows: int
    duplicate_rows_removed: int
    missing_url_rows_removed: int
    output_path: Path
    log_path: Path


def parse_args() -> argparse.Namespace:
    default_input, default_output_dir, default_output_file, default_log_file = _defaults()
    parser = argparse.ArgumentParser(
        description="Stage raw plant scrape output into a clean deduplicated CSV."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Path to the raw input CSV (default: knapsack/out/plants.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help="Directory where staging outputs should be written (default: plants/01_extract/out)",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=default_output_file,
        help="Name of the staged CSV file (default: stg_plants.csv)",
    )
    parser.add_argument(
        "--source-batch-id",
        type=str,
        default="knapsack_world_id_2026_04_17",
        help="Batch identifier to add/fill in the source_batch_id column",
        # required=True,
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=default_log_file,
        help="Name of the extraction log file (default: extract_plants.log)",
    )
    return parser.parse_args()



def read_csv_rows(input_path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Input CSV has no header row: {input_path}")
        fieldnames = list(reader.fieldnames)
        rows = [dict(row) for row in reader]

    return fieldnames, rows


def trim_outer_whitespace(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value.strip()


def normalize_row_values(row: Dict[str, str]) -> Dict[str, str]:
    """
    Trim obvious outer whitespace only. Inner whitespace and content are preserved.
    """
    return {key: trim_outer_whitespace(value) for key, value in row.items()}


def stable_row_hash(row: Dict[str, str], ordered_columns: Sequence[str]) -> str:
    """
    Build a stable hash from row contents using a deterministic column order.
    Excludes raw_hash itself from hashing.
    """
    parts: List[str] = []
    for col in ordered_columns:
        if col == "raw_hash":
            continue
        value = row.get(col, "")
        parts.append(f"{col}={value}")
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def ensure_source_batch_id(row: Dict[str, str], source_batch_id: str) -> Dict[str, str]:
    """
    Add source_batch_id if missing, or fill blanks with the provided batch id.
    """
    updated = dict(row)
    existing = updated.get("source_batch_id", "")
    if "source_batch_id" not in updated or not trim_outer_whitespace(existing):
        updated["source_batch_id"] = source_batch_id
    return updated


def dedupe_exact_rows(
    rows: Iterable[Dict[str, str]],
    ordered_columns: Sequence[str],
) -> Tuple[List[Dict[str, str]], int]:
    """
    Remove exact duplicate rows only, based on the full normalized row payload.
    """
    seen: set[str] = set()
    unique_rows: List[Dict[str, str]] = []
    duplicates_removed = 0

    for row in rows:
        row_hash = stable_row_hash(row, ordered_columns)
        if row_hash in seen:
            duplicates_removed += 1
            continue
        seen.add(row_hash)
        unique_rows.append(row)

    return unique_rows, duplicates_removed


def build_output_fieldnames(input_fieldnames: Sequence[str]) -> List[str]:
    fieldnames = list(input_fieldnames)
    if "source_batch_id" not in fieldnames:
        fieldnames.append("source_batch_id")
    if "raw_hash" not in fieldnames:
        fieldnames.append("raw_hash")
    return fieldnames


def stage_plants(
    input_path: Path,
    output_dir: Path,
    output_file: str,
    source_batch_id: str,
    log_file: str,
) -> ExtractResult:
    logging.info("Reading input file: %s", input_path)
    input_fieldnames, raw_rows = read_csv_rows(input_path)
    input_row_count = len(raw_rows)

    # Normalize values as lightly as possible and filter out missing URLs
    normalized_rows: List[Dict[str, str]] = []
    missing_url_count = 0

    for row in raw_rows:
        cleaned = normalize_row_values(row)

        # Filter out rows with missing URLs
        if not cleaned.get("detail_url"):
            missing_url_count += 1
            continue

        cleaned = ensure_source_batch_id(cleaned, source_batch_id)
        normalized_rows.append(cleaned)

    if missing_url_count > 0:
        logging.warning(
            f"Dropped {missing_url_count} rows because 'detail_url' was missing."
        )

    # Build field order for hashing and output.
    output_fieldnames = build_output_fieldnames(input_fieldnames)
    hash_columns = output_fieldnames[:]  # use final column order for stable hashing

    # Add raw_hash after all other fields are available.
    rows_with_hash: List[Dict[str, str]] = []
    for row in normalized_rows:
        row_copy = dict(row)
        row_copy["raw_hash"] = stable_row_hash(row_copy, hash_columns)
        rows_with_hash.append(row_copy)

    # Remove exact duplicates only.
    unique_rows, duplicates_removed = dedupe_exact_rows(rows_with_hash, hash_columns)

    ensure_dir(output_dir)
    output_path = output_dir / output_file
    log_path = output_dir / log_file

    logging.info("Writing staged CSV: %s", output_path)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in unique_rows:
            # Ensure every expected column exists and blank-fill missing values.
            output_row = {col: row.get(col, "") for col in output_fieldnames}
            writer.writerow(output_row)

    logging.info(
        "Extraction complete. input_rows=%d output_rows=%d duplicates_removed=%d",
        input_row_count,
        len(unique_rows),
        duplicates_removed,
    )

    return ExtractResult(
        input_rows=input_row_count,
        output_rows=len(unique_rows),
        duplicate_rows_removed=duplicates_removed,
        missing_url_rows_removed=missing_url_count,
        output_path=output_path,
        log_path=log_path,
    )


def write_summary_log(
    result: ExtractResult, source_batch_id: str, input_path: Path
) -> None:
    """
    Append a small human-readable log summary to the existing log file.
    The logging handler already writes the main log; this function adds a concise
    audit block for easy inspection.
    """
    summary_lines = [
        "",
        "=== EXTRACT SUMMARY ===",
        f"timestamp_utc={datetime.now(timezone.utc).isoformat()}",
        f"input_path={input_path}",
        f"output_path={result.output_path}",
        f"source_batch_id={source_batch_id}",
        f"input_rows={result.input_rows}",
        f"output_rows={result.output_rows}",
        f"duplicate_rows_removed={result.duplicate_rows_removed}",
        f"missing_url_rows_removed={result.missing_url_rows_removed}",
        "status=success",
        "=======================",
        "",
    ]
    with result.log_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))


def main() -> int:
    args = parse_args()
    cfg = load_settings("plants")
    ensure_dir(args.output_dir)
    log = shared_setup_logging("plants.01_extract", cfg)

    log.info("Starting 01_extract")
    log.info("Log file: %s", args.output_dir / args.log_file)

    try:
        result = stage_plants(
            input_path=args.input,
            output_dir=args.output_dir,
            output_file=args.output_file,
            source_batch_id=args.source_batch_id,
            log_file=args.log_file,
        )
        write_summary_log(result, args.source_batch_id, args.input)
        log.info("Done.")
        return 0
    except Exception as exc:
        logging.exception("Extraction failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
