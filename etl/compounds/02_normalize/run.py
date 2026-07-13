"""Normalize staged compound records and prepare them for enrichment and canonical building.

Purpose
-------
This script is the second step of the compound ETL pipeline. It consumes the staged
output from `01_extract`, normalizes text and identifier fields, prepares lookup keys
for compound matching, and validates CAS numbers. It reads the canonical `plant_id`
already attached in `01_extract` and classifies each row as mapped or unmapped; it
does not perform a fresh plant lookup of its own.

Inputs
------
- Staged compound CSV produced by `01_extract` (already carries `canonical_plant_id`).
- Settings from `settings.yml`.

Outputs
-------
- A normalized compound staging CSV in the step `out/` folder.
- A plant mapping resolution CSV in the step `out/` folder.
- A review CSV for unresolved or low-confidence plant mappings in the step `out/` folder.
- An optional summary JSON with counts and status breakdowns.
- A log file in the step `out/logs/` folder.

Behavior
--------
- Normalizes metabolite names, CAS IDs, formulas, weights, and lookup keys.
- Preserves raw values alongside normalized values.
- Reads the canonical `plant_id` attached in `01_extract` and marks each row mapped or
  unmapped (it does not perform a fresh plant lookup).
- Sends rows with an unresolved plant mapping, an invalid CAS checksum, or a missing
  metabolite name to review instead of dropping them.
- Does not deduplicate compounds.
- Does not query PubChem or ChEMBL.
- Is idempotent and safe to rerun with the same inputs and settings.

The script is intentionally chemistry-first: it prepares identity fields and plant
linkage fields for later enrichment and canonical compound building, but does not
attempt to decide the final canonical compound identity.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
import argparse
import csv
import hashlib
import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from shared.identity import normalize_cas as _normalize_cas_single
from shared.utils import (
    ETL_ROOT,
    ensure_dir,
    load_settings,
    make_run_id,
    normalize_whitespace,
    now_iso,
    to_key,
    write_csv,
    write_json,
)

RAW_COLUMNS = [
    "plant_id",
    "c_id",
    "cas_id",
    "metabolite",
    "molecular_formula",
    "mw",
    "organism",
    "canonical_plant_id",
    "plant_mapping_status",
    "plant_mapping_source_column",
    "plant_mapping_canonical_column",
]

NORMALIZED_COLUMNS = RAW_COLUMNS + [
    "normalized_metabolite_name",
    "normalized_metabolite_key",
    "normalized_cas_id",
    "normalized_cas_key",
    "cas_is_valid",
    "cas_validation_reason",
    "normalized_formula",
    "normalized_formula_key",
    "normalized_mw",
    "source_compound_key",
    "raw_plant_key",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
    "raw_line_number",
    "raw_row_hash",
    "normalization_status",
    "review_reason",
]


def setup_logging(log_dir: Path, run_id: str) -> Path:
    ensure_dir(log_dir)
    log_path = log_dir / f"normalize_compounds_{run_id}.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return log_path


def stable_hash(payload: Dict[str, Any]) -> str:
    """SHA-256 dedup fingerprint — kept as SHA-256 intentionally."""
    canonical_json = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def canonicalize_formula(value: Optional[str]) -> str:
    if not value:
        return ""
    text = normalize_whitespace(value)
    text = text.replace(" ", "")
    return text


def format_mw(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = normalize_whitespace(value)
    if not text:
        return ""
    try:
        num = float(text)
        if math.isnan(num) or math.isinf(num):
            return ""
        formatted = f"{num:.6f}".rstrip("0").rstrip(".")
        return formatted if formatted else "0"
    except ValueError:
        return text


def normalize_name(value: Optional[str]) -> str:
    if value is None:
        return ""
    return normalize_whitespace(value)


def normalize_cas(value: Optional[str]) -> Tuple[str, bool, str]:
    """Normalize possibly-comma-separated CAS input; return first valid part."""
    if not value:
        return "", False, "missing"
    raw_parts = [p.strip() for p in str(value).split(",")]
    first_norm, first_reason = raw_parts[0], "invalid_format"
    for part in raw_parts:
        normalized, is_valid, reason = _normalize_cas_single(part)
        if is_valid:
            return normalized, True, "ok"
        first_norm = first_norm or normalized
    return first_norm, False, first_reason


def ensure_columns(fieldnames: List[str]) -> None:
    missing = [c for c in RAW_COLUMNS if c not in fieldnames]
    if missing:
        raise ValueError(f"Missing expected columns in staged input: {missing}")


def normalize_row(
    row: Dict[str, str],
    raw_line_number: int,
    run_id: str,
    source_name: str,
    source_url: str,
    batch_id: str,
) -> Dict[str, Any]:
    raw = {k: normalize_whitespace(row.get(k, "")) for k in RAW_COLUMNS}
    raw_name = raw["metabolite"]
    normalized_name = normalize_name(raw_name)
    normalized_name_key = to_key(normalized_name)

    normalized_cas_id, cas_valid, cas_reason = normalize_cas(raw["cas_id"])
    normalized_cas_key = to_key(normalized_cas_id)

    normalized_formula = canonicalize_formula(raw["molecular_formula"])
    normalized_formula_key = to_key(normalized_formula)
    normalized_mw = format_mw(raw["mw"])

    raw_plant_key = to_key(raw["plant_id"])
    canonical_plant_id = normalize_whitespace(row.get("canonical_plant_id", ""))
    plant_status = "mapped" if canonical_plant_id else "unmapped"

    review_reasons: List[str] = []
    if not canonical_plant_id:
        review_reasons.append("unresolved_plant_mapping")
    if not cas_valid and raw["cas_id"]:
        review_reasons.append(f"cas_{cas_reason}")
    if not normalized_name:
        review_reasons.append("missing_metabolite_name")

    if review_reasons:
        normalization_status = "review"
        review_reason = ";".join(review_reasons)
    else:
        normalization_status = "ready"
        review_reason = ""

    source_compound_key = stable_hash(
        {
            "plant_id": raw["plant_id"],
            "c_id": raw["c_id"],
            "cas_id": raw["cas_id"],
            "metabolite": raw["metabolite"],
            "molecular_formula": raw["molecular_formula"],
            "mw": raw["mw"],
            "organism": raw["organism"],
        }
    )

    retrieved_at = batch_id if batch_id and batch_id != "auto" else now_iso()

    normalized_payload = {
        **raw,
        "normalized_metabolite_name": normalized_name,
        "normalized_metabolite_key": normalized_name_key,
        "normalized_cas_id": normalized_cas_id,
        "normalized_cas_key": normalized_cas_key,
        "cas_is_valid": str(cas_valid).lower(),
        "cas_validation_reason": cas_reason,
        "normalized_formula": normalized_formula,
        "normalized_formula_key": normalized_formula_key,
        "normalized_mw": normalized_mw,
        "source_compound_key": source_compound_key,
        "raw_plant_key": raw_plant_key,
        "canonical_plant_id": canonical_plant_id,
        "plant_mapping_status": plant_status,
        "source_name": source_name,
        "source_url": source_url,
        "source_batch_id": run_id,
        "retrieved_at": retrieved_at,
        "raw_line_number": raw_line_number,
        "raw_row_hash": row.get("raw_row_hash", ""),
        "normalization_status": normalization_status,
        "review_reason": review_reason,
    }
    return normalized_payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize staged compound rows and prepare plant mappings."
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "settings.yml"),
        help="Path to the compound ETL settings.yml file.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="",
        help="Optional override for the staged compound input CSV.",
    )
    args = parser.parse_args()

    cfg = load_settings("compounds")
    run_id = make_run_id("compounds")

    paths = cfg.get("paths", {})
    step_dirs = paths.get("step_dirs", {})
    source_cfg = cfg.get("source", {})

    extract_out_dir = ETL_ROOT / step_dirs["extract_out"]
    normalize_out_dir = ETL_ROOT / step_dirs["normalize_out"]
    normalize_log_dir = normalize_out_dir / "logs"

    source_name = str(source_cfg.get("name", "KNApSAcK"))
    source_url = str(source_cfg.get("url", ""))
    batch_id = str(cfg.get("source", {}).get("batch_id", "auto"))

    log_path = setup_logging(normalize_log_dir, run_id)
    log = logging.getLogger("compounds.02_normalize")

    input_file = (
        Path(args.input).resolve() if args.input else extract_out_dir / "plants_compounds_staged.csv"
    )
    log.info("Starting compound normalization run_id=%s", run_id)
    log.info("Input file: %s", input_file)

    if not input_file.exists():
        raise FileNotFoundError(f"Staged input file not found: {input_file}")

    with input_file.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Input file has no header row.")
        ensure_columns(reader.fieldnames)
        staged_rows = list(reader)

    normalized_rows = [
        normalize_row(row, idx + 2, run_id, source_name, source_url, batch_id)
        for idx, row in enumerate(staged_rows)
    ]
    review_rows = [r for r in normalized_rows if r["normalization_status"] == "review"]
    mapping_rows = [
        {
            "source_plant_raw_id": r["plant_id"],
            "raw_plant_key": r["raw_plant_key"],
            "canonical_plant_id": r["canonical_plant_id"],
            "plant_mapping_status": r["plant_mapping_status"],
            "source_name": r["source_name"],
            "source_batch_id": r["source_batch_id"],
            "retrieved_at": r["retrieved_at"],
            "raw_line_number": r["raw_line_number"],
            "raw_row_hash": r["raw_row_hash"],
        }
        for r in normalized_rows
    ]

    ensure_dir(normalize_out_dir)
    normalized_out = normalize_out_dir / "compounds_normalized.csv"
    mapping_out = normalize_out_dir / "plant_mapping_resolution.csv"
    review_out = normalize_out_dir / "compound_review.csv"
    summary_out = normalize_out_dir / "normalize_compounds_summary.json"

    write_csv(normalized_rows, normalized_out, NORMALIZED_COLUMNS)
    write_csv(
        mapping_rows,
        mapping_out,
        [
            "source_plant_raw_id",
            "raw_plant_key",
            "canonical_plant_id",
            "plant_mapping_status",
            "source_name",
            "source_batch_id",
            "retrieved_at",
            "raw_line_number",
            "raw_row_hash",
        ],
    )
    write_csv(review_rows, review_out, NORMALIZED_COLUMNS)

    summary = {
        "module": "compounds",
        "step": "02_normalize",
        "run_id": run_id,
        "input_file": str(input_file),
        "output_file": str(normalized_out),
        "mapping_file": str(mapping_out),
        "review_file": str(review_out),
        "row_count": len(normalized_rows),
        "review_row_count": len(review_rows),
        "status_counts": {
            "ready": sum(
                1 for r in normalized_rows if r["normalization_status"] == "ready"
            ),
            "review": len(review_rows),
        },
        "cas_valid_count": sum(
            1 for r in normalized_rows if r["cas_is_valid"] == "true"
        ),
        "cas_invalid_count": sum(
            1 for r in normalized_rows if r["cas_is_valid"] == "false"
        ),
        "generated_at": now_iso(),
        "log_file": str(log_path),
    }
    write_json(summary, summary_out)
    summary["summary_file"] = str(summary_out)

    log.info("Normalized rows: %d", len(normalized_rows))
    log.info("Review rows: %d", len(review_rows))
    log.info("Normalized output: %s", normalized_out)
    log.info("Mapping output: %s", mapping_out)
    log.info("Review output: %s", review_out)
    log.info("Summary output: %s", summary_out)
    log.info("Completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
