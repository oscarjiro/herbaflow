"""Export step for the refactored disease ETL pipeline.

Purpose
-------
Export the final disease tables in import-ready form for Supabase/PostgreSQL.
This step copies the canonical disease outputs into a stable export directory
and prepares files for future disease-target ETL.

Inputs
------
- diseases/settings.yml for configuration and export behavior
- diseases/04_validate/out/ when validation artifacts are present
- diseases/03_build_canonical/out/ as the fallback source for the tables

Outputs
-------
- final diseases.csv
- final disease_aliases.csv
- final disease_alias_map.csv
- final disease_targets_template.csv when present

Behavior
--------
- Preserves stable column order from settings.yml when configured, otherwise
  keeps the source column order
- Does not mutate upstream files
- Prefers validated outputs when they exist, but falls back to canonical build
  outputs for the actual table data
- Can fail if validation has failed and the config requires a passing validation
  report
- Is idempotent and safe to rerun from the command line
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir, now_iso

from diseases.utils import (
    read_csv,
    safe_str,
    write_csv,
)

DEFAULT_SETTINGS_PATH = ETL_ROOT / "diseases" / "settings.yml"
DEFAULT_VALIDATE_DIR = ETL_ROOT / "diseases" / "04_validate" / "out"
DEFAULT_CANONICAL_DIR = ETL_ROOT / "diseases" / "03_build_canonical" / "out"
DEFAULT_EXPORT_DIR = ETL_ROOT / "diseases" / "05_export" / "out"

TABLE_FILES = {
    "diseases": "diseases.csv",
    "disease_aliases": "disease_aliases.csv",
    "disease_alias_map": "disease_alias_map.csv",
    "disease_targets_template": "disease_targets_template.csv",
}


def _resolve_path(base_dir: Path, raw_value: str, default_value: str) -> Path:
    """Resolve a configured path relative to the project root."""
    path = Path(raw_value or default_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _resolve_paths(
    settings: dict[str, Any], settings_path: Path
) -> tuple[Path, Path, Path]:
    """Resolve validation, canonical, and export paths."""
    paths = settings.get("paths", {})
    validate_out = _resolve_path(
        ETL_ROOT,
        str(paths.get("validate_out", "diseases/04_validate/out")),
        "diseases/04_validate/out",
    )
    canonical_out = _resolve_path(
        ETL_ROOT,
        str(paths.get("canonical_out", "diseases/03_build_canonical/out")),
        "diseases/03_build_canonical/out",
    )
    export_out = _resolve_path(
        ETL_ROOT,
        str(paths.get("export_out", "diseases/05_export/out")),
        "diseases/05_export/out",
    )
    return validate_out, canonical_out, export_out


def _validation_passed(validate_out: Path) -> bool | None:
    """Read validation summary if present and return pass/fail status."""
    report_path = validate_out / "validation_report.json"
    if not report_path.exists():
        return None

    try:
        with report_path.open("r", encoding="utf-8") as f:
            report = json.load(f)
    except Exception:
        return None

    return bool(report.get("passed", False))


def _resolve_source_file(
    preferred_dir: Path, fallback_dir: Path, filename: str
) -> Path | None:
    """Resolve a source CSV from the preferred directory, then the fallback."""
    primary = preferred_dir / filename
    if primary.exists():
        return primary

    fallback = fallback_dir / filename
    if fallback.exists():
        return fallback

    return None


def _column_order_for(
    table_key: str,
    df: pd.DataFrame,
    export_cfg: dict[str, Any],
) -> list[str]:
    """Determine the stable output column order for a table."""
    schema_order = export_cfg.get("column_order", {})
    configured = (
        schema_order.get(table_key, []) if isinstance(schema_order, dict) else []
    )
    if configured:
        ordered = [col for col in configured if col in df.columns]
        remaining = [col for col in df.columns if col not in ordered]
        return ordered + remaining
    return list(df.columns)


def _copy_table(
    *,
    table_key: str,
    source_dir: Path,
    fallback_dir: Path,
    export_dir: Path,
    export_cfg: dict[str, Any],
) -> tuple[str, int] | None:
    """Copy one table to the export directory."""
    filename = TABLE_FILES[table_key]
    source_path = _resolve_source_file(source_dir, fallback_dir, filename)
    if source_path is None:
        return None

    df = read_csv(source_path)
    ordered = _column_order_for(table_key, df, export_cfg)
    out_path = export_dir / filename
    write_csv(df[ordered], out_path)

    return str(out_path), int(len(df))


def _write_export_notes(path: Path, manifest: dict[str, Any]) -> None:
    """Write a small human-readable export summary."""
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        f.write(f"Export completed at {manifest['timestamp']}\n")
        f.write(f"Source directory: {manifest['source_dir']}\n")
        f.write(f"Validation passed: {manifest['validation_passed']}\n")
        if manifest.get("exported_files"):
            f.write("Exported files:\n")
            for key, value in manifest["exported_files"].items():
                f.write(f"- {key}: {value}\n")


def run(settings_path: str | Path = DEFAULT_SETTINGS_PATH) -> dict[str, Any]:
    """Run the export step and return a summary dictionary."""
    settings_path = Path(settings_path)
    settings = load_settings("diseases")
    logger = shared_setup_logging("diseases.05_export", settings)

    validate_out, canonical_out, export_out = _resolve_paths(settings, settings_path)
    ensure_dir(export_out)

    export_cfg = settings.get("export", {})
    write_notes_flag = bool(export_cfg.get("write_notes", True))
    require_validation_pass = bool(export_cfg.get("require_validation_pass", True))

    validation_status = _validation_passed(validate_out)
    if validation_status is False and require_validation_pass:
        raise ValueError(
            f"Validation report in {validate_out} indicates failure. "
            f"Export halted because export.require_validation_pass is enabled."
        )

    source_dir = (
        validate_out
        if any((validate_out / fn).exists() for fn in TABLE_FILES.values())
        else canonical_out
    )

    exported_files: dict[str, str] = {}
    row_counts: dict[str, int] = {}
    missing_sources: list[str] = []

    for table_key in (
        "diseases",
        "disease_aliases",
        "disease_alias_map",
        "disease_targets_template",
    ):
        result = _copy_table(
            table_key=table_key,
            source_dir=source_dir,
            fallback_dir=canonical_out,
            export_dir=export_out,
            export_cfg=export_cfg,
        )
        if result is None:
            if table_key != "disease_targets_template":
                missing_sources.append(TABLE_FILES[table_key])
            continue
        out_path, row_count = result
        exported_files[table_key] = out_path
        row_counts[table_key] = row_count

    manifest = {
        "module_name": settings.get("module_name", "disease_etl"),
        "step": "05_export",
        "batch_id": settings.get("batch_id", ""),
        "source_dir": str(source_dir),
        "canonical_out": str(canonical_out),
        "validate_out": str(validate_out),
        "export_out": str(export_out),
        "validation_passed": validation_status,
        "exported_files": exported_files,
        "row_counts": row_counts,
        "missing_sources": missing_sources,
        "timestamp": now_iso(),
    }

    manifest_path = export_out / "run_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if write_notes_flag:
        _write_export_notes(export_out / "export_notes.txt", manifest)

    log_path = export_out / "run.log"
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"Export completed at {manifest['timestamp']}\n")
        f.write(f"Source dir: {source_dir}\n")
        f.write(f"Export dir: {export_out}\n")
        f.write(f"Validation passed: {validation_status}\n")
        for name, out_path in exported_files.items():
            f.write(f"{name}: {out_path}\n")

    logger.info(
        "Export complete: %s",
        ", ".join(exported_files.values()) or "no files written",
    )
    return manifest


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export final disease tables in import-ready form for Supabase/PostgreSQL."
    )
    parser.add_argument(
        "--settings",
        default=str(DEFAULT_SETTINGS_PATH),
        help="Path to the pipeline settings.yml file (default: diseases/settings.yml)",
    )
    args = parser.parse_args()
    run(args.settings)


if __name__ == "__main__":
    main()
