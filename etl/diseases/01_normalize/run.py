"""Disease normalization step for the ETL pipeline.

Purpose
-------
Clean and standardize disease names, aliases, and simple reference-like text
fields from the raw seed output. This step prepares the data for ontology
mapping and canonical table construction, but does not perform those later
steps.

Inputs
------
- settings.yml for pipeline configuration and paths
- diseases/01_normalize/in/disease_seed.csv by default

Outputs
-------
- A normalized CSV written to diseases/01_normalize/out/
- A small run manifest in the same out/ directory

Behavior
--------
- Preserves original raw columns and values
- Adds clean companion fields such as disease_name_clean, disease_key,
  synonym_clean, and source_reference_clean when relevant columns are present
- Standardizes whitespace, casing, punctuation, and canonical key generation
- Does not perform ontology mapping or create canonical rows
- Is idempotent and safe to rerun
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir, now_iso

from diseases.utils import (
    canonical_key,
    normalize_text,
    read_csv,
    safe_str,
    write_csv,
    SETTINGS_PATH,
)

NAME_COLUMNS = ("disease_name", "disease", "name", "condition", "disease_label")
SYNONYM_COLUMNS = ("synonym", "synonyms", "alias", "aliases", "other_names")
REFERENCE_COLUMNS = ("source_reference", "reference", "refs", "citation", "literature")


def _resolve_paths(settings: dict[str, Any]) -> tuple[Path, Path]:
    """Resolve the configured normalize input and output paths."""
    paths = settings.get("paths", {})
    normalize_in = Path(paths.get("normalize_input", "diseases/01_normalize/in"))
    normalize_out = Path(paths.get("normalize_out", "diseases/01_normalize/out"))

    if not normalize_in.is_absolute():
        normalize_in = (ETL_ROOT / normalize_in).resolve()
    if not normalize_out.is_absolute():
        normalize_out = (ETL_ROOT / normalize_out).resolve()

    return normalize_in, normalize_out


def _pick_first_existing(
    columns: Iterable[str], candidates: Iterable[str]
) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _normalize_name_value(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    text = re.sub(r"\s*[/|,;]+\s*", "; ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_synonym_value(value: object) -> str:
    text = safe_str(value)
    if not text:
        return ""
    parts = [part.strip() for part in re.split(r"[;|,/]", text) if part.strip()]
    if not parts:
        return ""
    cleaned = [re.sub(r"\s+", " ", normalize_text(part)) for part in parts]
    cleaned = [part for part in cleaned if part]
    return "; ".join(cleaned)


def _normalize_reference_value(value: object) -> str:
    text = safe_str(value)
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*\(.*?\)\s*$", "", text).strip()
    return text


def run(settings_path: str | Path = SETTINGS_PATH) -> dict[str, Any]:
    """Run the normalization step and return a small summary dictionary."""
    settings_path = Path(settings_path)
    settings = load_settings("diseases")
    logger = shared_setup_logging("diseases.01_normalize", settings)

    normalize_in, normalize_out = _resolve_paths(settings)
    ensure_dir(normalize_out)

    if not normalize_in.exists():
        candidates = sorted(normalize_in.glob("*.csv"))
        if len(candidates) == 1:
            normalize_in = candidates[0]
        else:
            raise FileNotFoundError(
                f"Could not resolve normalized input CSV in {normalize_in}. Expected disease_seed.csv or a single CSV file."
            )

    df = read_csv(normalize_in)
    df_out = df.copy()

    name_col = _pick_first_existing(df_out.columns, NAME_COLUMNS)
    synonym_col = _pick_first_existing(df_out.columns, SYNONYM_COLUMNS)
    reference_col = _pick_first_existing(df_out.columns, REFERENCE_COLUMNS)

    if name_col is not None:
        df_out["disease_name_clean"] = df_out[name_col].map(_normalize_name_value)
        df_out["disease_key"] = df_out["disease_name_clean"].map(canonical_key)
    else:
        df_out["disease_name_clean"] = ""
        df_out["disease_key"] = ""

    if synonym_col is not None:
        df_out["synonym_clean"] = df_out[synonym_col].map(_normalize_synonym_value)
    elif "synonym_clean" not in df_out.columns:
        df_out["synonym_clean"] = ""

    if reference_col is not None:
        df_out["source_reference_clean"] = df_out[reference_col].map(
            _normalize_reference_value
        )
    elif "source_reference_clean" not in df_out.columns:
        df_out["source_reference_clean"] = ""

    # Keep row-level provenance available for later steps.
    source_cfg = settings.get("source", {})
    if "batch_id" not in df_out.columns:
        df_out["batch_id"] = safe_str(source_cfg.get("batch_id", ""))
    if "source_name" not in df_out.columns:
        df_out["source_name"] = safe_str(source_cfg.get("name", ""))
    if "source_url" not in df_out.columns:
        df_out["source_url"] = safe_str(source_cfg.get("url", ""))
    if "retrieved_at" not in df_out.columns:
        df_out["retrieved_at"] = safe_str(source_cfg.get("retrieved_at", ""))

    output_path = normalize_out / normalize_in.name
    write_csv(df_out, output_path)

    manifest = {
        "module_name": settings.get("module", {}).get("name", "diseases"),
        "step": "01_normalize",
        "batch_id": settings.get("source", {}).get("batch_id", ""),
        "input_path": str(normalize_in),
        "output_path": str(output_path),
        "row_count": int(len(df_out)),
        "column_names": list(df_out.columns),
        "name_column": name_col,
        "synonym_column": synonym_col,
        "reference_column": reference_col,
        "timestamp": now_iso(),
    }

    manifest_path = normalize_out / "run_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    log_path = normalize_out / "run.log"
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"Normalization completed at {manifest['timestamp']}\n")
        f.write(f"Input: {normalize_in}\n")
        f.write(f"Output: {output_path}\n")
        f.write(f"Rows: {len(df_out)}\n")
        f.write(f"Columns: {', '.join(df_out.columns)}\n")

    logger.info("Normalized disease seed: %s rows -> %s", len(df_out), output_path)
    return manifest


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Normalize disease seed rows for downstream mapping and canonical build."
    )
    parser.add_argument(
        "--settings",
        default=SETTINGS_PATH,
        help="Path to the pipeline settings.yml file (default: settings.yml)",
    )
    args = parser.parse_args()
    run(args.settings)


if __name__ == "__main__":
    main()
