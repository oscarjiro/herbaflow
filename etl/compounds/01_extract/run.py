"""Extract raw compound records from KNApSAcK into a staged, provenance-rich CSV.

Purpose
-------
This script is the first step of the compound ETL pipeline. It reads the immutable
raw source file `knapsack/out/plants_compounds.csv`, preserves every raw row as
source evidence, standardizes whitespace only in text fields, and attaches minimal
provenance metadata for downstream normalization and enrichment steps.

Inputs
------
- Raw compound source file configured in `settings.yml`.
- Batch/run metadata configured in `settings.yml`.
- The finished plant ETL export `plants.csv` when raw-to-canonical plant mapping
  is needed.

Outputs
-------
- `plants_compounds_staged.csv` in the step `out/` folder.
- `extract_compounds_manifest.json` in the step `out/` folder.
- A log file in the step `out/logs/` folder.
- A settings snapshot in the step `out/` folder for reproducibility.

Behavior
--------
- Does not deduplicate rows.
- Does not enrich compounds.
- Does not attempt canonical chemical matching.
- Preserves raw source traceability by keeping original raw values alongside
  provenance metadata.
- Standardizes whitespace only in text fields.
- Uses the plant ETL export only to resolve raw plant references to canonical
  `plant_id` values when possible.
- Produces stable hashes and stable row identifiers so reruns with the same input
  and batch metadata yield identical outputs.

The script is intentionally conservative and only preserves raw source evidence
for later normalization and review.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir, normalize_whitespace, make_run_id, write_csv, write_json, now_iso

import argparse
import csv
import hashlib
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

EXPECTED_RAW_COLUMNS = [
    "plant_id",
    "c_id",
    "cas_id",
    "metabolite",
    "molecular_formula",
    "mw",
    "organism",
]

PLANT_RAW_ID_CANDIDATES = [
    "source_plant_raw_id",
    "raw_plant_id",
    "original_plant_id",
    "knapsack_plant_id",
    "source_plant_id",
    "scraped_plant_id",
    "source_id",
]

PLANT_CANONICAL_ID_CANDIDATES = ["plant_id", "canonical_plant_id"]


def setup_logging(log_dir: Path, run_id: str) -> Path:
    """Configure file + console logging and return the log path."""
    ensure_dir(log_dir)
    log_path = log_dir / f"extract_compounds_{run_id}.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return log_path


def stable_hash(payload: Dict[str, Any]) -> str:
    """Compute a stable SHA-256 hash from a JSON-serializable payload (used for row dedup fingerprinting)."""
    canonical_json = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def ensure_columns(fieldnames: List[str]) -> None:
    missing = [c for c in EXPECTED_RAW_COLUMNS if c not in fieldnames]
    if missing:
        raise ValueError(f"Missing expected raw columns: {missing}")


def load_plant_mapping(
    plants_csv: Optional[Path],
) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Any]]:
    """Load raw-to-canonical plant mappings from the finished plant ETL export."""
    if not plants_csv or not plants_csv.exists():
        return {}, {
            "mapping_file": str(plants_csv) if plants_csv else "",
            "loaded": False,
            "row_count": 0,
        }

    mapping: Dict[str, Dict[str, str]] = {}
    row_count = 0
    with plants_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return {}, {
                "mapping_file": str(plants_csv),
                "loaded": False,
                "row_count": 0,
            }

        field_set = set(reader.fieldnames)
        canonical_col = next(
            (c for c in PLANT_CANONICAL_ID_CANDIDATES if c in field_set), None
        )
        if canonical_col is None:
            return {}, {
                "mapping_file": str(plants_csv),
                "loaded": False,
                "row_count": 0,
                "reason": "no canonical plant id column found",
            }

        raw_col = next((c for c in PLANT_RAW_ID_CANDIDATES if c in field_set), None)
        if raw_col is None:
            return {}, {
                "mapping_file": str(plants_csv),
                "loaded": False,
                "row_count": 0,
                "reason": "no raw plant id column found",
            }

        for row in reader:
            row_count += 1
            raw_id = normalize_whitespace(row.get(raw_col, ""))
            canonical_id = normalize_whitespace(row.get(canonical_col, ""))
            if not raw_id or not canonical_id:
                continue
            mapping[raw_id] = {
                "canonical_plant_id": canonical_id,
                "plant_mapping_source_column": raw_col,
                "plant_mapping_canonical_column": canonical_col,
            }

    return mapping, {
        "mapping_file": str(plants_csv),
        "loaded": True,
        "row_count": row_count,
        "mapped_rows": len(mapping),
        "raw_id_column": raw_col,
        "canonical_id_column": canonical_col,
    }


def build_output_rows(
    rows: Iterable[Dict[str, str]],
    run_id: str,
    source_name: str,
    source_url: str,
    plant_mapping: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Create staged rows with raw evidence preserved and provenance metadata attached."""
    output_rows: List[Dict[str, Any]] = []
    retrieved_at = now_iso()

    for idx, raw_row in enumerate(rows, start=2):  # header is line 1
        standardized = {
            k: normalize_whitespace(raw_row.get(k, "")) for k in EXPECTED_RAW_COLUMNS
        }
        plant_id_value = standardized["plant_id"]
        plant_hit = plant_mapping.get(plant_id_value, {})

        raw_evidence_payload = {
            "plant_id": standardized["plant_id"],
            "c_id": standardized["c_id"],
            "cas_id": standardized["cas_id"],
            "metabolite": standardized["metabolite"],
            "molecular_formula": standardized["molecular_formula"],
            "mw": standardized["mw"],
            "organism": standardized["organism"],
            "source_name": source_name,
            "source_url": source_url,
            "source_batch_id": run_id,
            "raw_line_number": idx,
        }
        raw_hash = stable_hash(raw_evidence_payload)

        output_rows.append(
            {
                **standardized,
                "source_name": source_name,
                "source_url": source_url,
                "source_batch_id": run_id,
                "retrieved_at": retrieved_at,
                "raw_line_number": idx,
                "raw_row_hash": raw_hash,
                "canonical_plant_id": plant_hit.get("canonical_plant_id", ""),
                "plant_mapping_source_column": plant_hit.get(
                    "plant_mapping_source_column", ""
                ),
                "plant_mapping_canonical_column": plant_hit.get(
                    "plant_mapping_canonical_column", ""
                ),
                "plant_mapping_status": "mapped" if plant_hit else "unmapped",
            }
        )

    return output_rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract staged compound rows from raw KNApSAcK input."
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "settings.yml"),
        help="Path to the compound ETL settings.yml file.",
    )
    args = parser.parse_args()

    cfg = load_settings("compounds")
    run_id = make_run_id("compounds")

    paths = cfg.get("paths", {})
    step_dirs = paths.get("step_dirs", {})
    source_cfg = cfg.get("source", {})

    raw_input_file = ETL_ROOT / paths["raw"]["plants_compounds_csv"]
    extract_out_dir = ETL_ROOT / step_dirs["extract_out"]
    extract_log_dir = extract_out_dir / "logs"
    plant_export_csv_rel = paths.get("plant_etl", {}).get("canonical_plants_csv")
    plant_export_csv = ETL_ROOT / plant_export_csv_rel if plant_export_csv_rel else None

    source_name = str(source_cfg.get("name", "KNApSAcK"))
    source_url = str(source_cfg.get("url", ""))

    log_path = setup_logging(extract_log_dir, run_id)
    log = logging.getLogger("compounds.01_extract")

    log.info("Starting compound extraction run_id=%s", run_id)
    log.info("Raw input file: %s", raw_input_file)

    if not raw_input_file.exists():
        raise FileNotFoundError(f"Raw input file not found: {raw_input_file}")

    plant_mapping, plant_mapping_meta = load_plant_mapping(plant_export_csv)
    if plant_mapping_meta.get("loaded"):
        log.info(
            "Loaded plant mapping from %s (rows=%s, mapped=%s)",
            plant_mapping_meta.get("mapping_file"),
            plant_mapping_meta.get("row_count"),
            plant_mapping_meta.get("mapped_rows"),
        )
    elif plant_export_csv:
        log.info(
            "Plant export present but no usable mapping columns were found: %s",
            plant_export_csv,
        )

    with raw_input_file.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Raw input file has no header row.")
        ensure_columns(reader.fieldnames)
        raw_rows = list(reader)

    staged_rows = build_output_rows(raw_rows, run_id, source_name, source_url, plant_mapping)

    ensure_dir(extract_out_dir)
    output_file = extract_out_dir / "plants_compounds_staged.csv"
    manifest_file = extract_out_dir / "extract_compounds_manifest.json"
    settings_copy_file = extract_out_dir / f"settings_snapshot_{run_id}.yml"

    fieldnames = EXPECTED_RAW_COLUMNS + [
        "source_name",
        "source_url",
        "source_batch_id",
        "retrieved_at",
        "raw_line_number",
        "raw_row_hash",
        "canonical_plant_id",
        "plant_mapping_source_column",
        "plant_mapping_canonical_column",
        "plant_mapping_status",
    ]

    write_csv(staged_rows, output_file, fieldnames=fieldnames)

    settings_path = Path(args.settings).resolve()
    manifest = {
        "module": "compounds",
        "step": "01_extract",
        "run_id": run_id,
        "settings_file": str(settings_path),
        "source_name": source_name,
        "source_url": source_url,
        "raw_input_file": str(raw_input_file),
        "output_file": str(output_file),
        "row_count": len(staged_rows),
        "source_row_count": len(raw_rows),
        "expected_raw_columns": EXPECTED_RAW_COLUMNS,
        "plant_mapping": plant_mapping_meta,
        "log_file": str(log_path),
        "generated_at": now_iso(),
    }
    write_json(manifest, manifest_file)

    if not settings_copy_file.exists():
        with settings_path.open("r", encoding="utf-8") as src, settings_copy_file.open(
            "w", encoding="utf-8"
        ) as dst:
            dst.write(src.read())

    log.info("Wrote staged rows: %d", len(staged_rows))
    log.info("Output CSV: %s", output_file)
    log.info("Manifest: %s", manifest_file)
    log.info("Completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
