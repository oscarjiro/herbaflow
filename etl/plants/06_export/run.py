"""
06_export: prepare validated plant seed data for Supabase/PostgreSQL import.

Input folder:
    05_validate/out/   (override with --input-dir if your validated files live elsewhere)

Expected input files:
    plants.csv
    plant_aliases.csv

Outputs:
    06_export/out/plants.csv
    06_export/out/plant_aliases.csv
    06_export/out/export_manifest.json
    06_export/out/export.log
    06_export/out/plants.sql              (optional, with --emit-sql)
    06_export/out/plant_aliases.sql      (optional, with --emit-sql)

Features:
- preserves foreign-key-friendly IDs
- keeps output column order aligned with the intended Supabase schema
- optional SQL generation
- dry-run mode
- idempotent reruns (overwrites outputs deterministically)
- manifest with source files, row counts, and timestamps

Run:
    python export_seed_files.py \
        --input-dir 05_validate/out \
        --output-dir 06_export/out \
        --emit-sql
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir

import argparse
import csv
import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd


DEFAULT_PLANTS_SQL_FILE = "plants.sql"
DEFAULT_ALIASES_SQL_FILE = "plant_aliases.sql"


def _defaults() -> dict:
    cfg = load_settings("plants")
    return cfg["paths"]["export"]

PLANTS_SCHEMA_COLUMNS = [
    "plant_id",
    "raw_plant_id",
    "canonical_key",
    "canonical_scientific_name",
    "authorship",
    "family_name",
    "taxonomic_status",
    "rank",
    "gbif_usage_key",
    "gbif_accepted_usage_key",
    "gbif_species_key",
    "gbif_genus_key",
    "gbif_family_key",
    "gbif_kingdom_key",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
    "confidence",
]

ALIASES_SCHEMA_COLUMNS = [
    "alias_id",
    "plant_id",
    "alias_name",
    "alias_key",
    "alias_type",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
]

ID_LIKE_COLUMNS = {
    "plant_id",
    "raw_plant_id",
    "alias_id",
    "gbif_usage_key",
    "gbif_accepted_usage_key",
    "gbif_species_key",
    "gbif_genus_key",
    "gbif_family_key",
    "gbif_kingdom_key",
}

WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ExportResult:
    plants_input_rows: int
    aliases_input_rows: int
    plants_output_rows: int
    aliases_output_rows: int
    output_dir: Path
    plants_path: Path
    aliases_path: Path
    manifest_path: Path
    log_path: Path
    plants_sql_path: Optional[Path] = None
    aliases_sql_path: Optional[Path] = None


def parse_args() -> argparse.Namespace:
    step = _defaults()
    parser = argparse.ArgumentParser(
        description="Prepare validated plant seed data for Supabase/PostgreSQL import."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=ETL_ROOT / step["input_dir"],
        help="Folder containing validated plants.csv and plant_aliases.csv (default: plants/05_validate/out)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ETL_ROOT / step["output_dir"],
        help="Folder to write export files into (default: plants/06_export/out)",
    )
    parser.add_argument(
        "--plants-file",
        type=str,
        default=step["plants_file"],
        help="Filename for exported plants CSV (default: plants.csv)",
    )
    parser.add_argument(
        "--aliases-file",
        type=str,
        default=step["aliases_file"],
        help="Filename for exported aliases CSV (default: plant_aliases.csv)",
    )
    parser.add_argument(
        "--manifest-file",
        type=str,
        default=step["manifest_file"],
        help="Filename for export manifest JSON (default: export_manifest.json)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=step["log_file"],
        help="Filename for export log (default: export.log)",
    )
    parser.add_argument(
        "--emit-sql",
        action="store_true",
        help="Also write SQL INSERT files for plants and plant_aliases.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and summarize only; do not write export files.",
    )
    parser.add_argument(
        "--plants-sql-file",
        type=str,
        default=DEFAULT_PLANTS_SQL_FILE,
        help="Filename for plants SQL file when --emit-sql is used (default: plants.sql)",
    )
    parser.add_argument(
        "--aliases-sql-file",
        type=str,
        default=DEFAULT_ALIASES_SQL_FILE,
        help="Filename for plant_aliases SQL file when --emit-sql is used (default: plant_aliases.sql)",
    )
    return parser.parse_args()



def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_id_like(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    lower = text.lower()
    if lower in {"nan", "none", "null"}:
        return ""
    try:
        num = float(text)
        if math.isfinite(num) and num.is_integer():
            return str(int(num))
        return format(num, ".15g")
    except Exception:
        pass
    if re.fullmatch(r"[+-]?\d+", text):
        return str(int(text))
    return text


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)


def ensure_required_columns(
    df: pd.DataFrame, required: Sequence[str], table_name: str
) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{table_name} is missing required columns: {', '.join(missing)}"
        )


def canonicalize_df(df: pd.DataFrame, required_columns: Sequence[str]) -> pd.DataFrame:
    """
    Keep only schema columns, in the exact intended order.
    Missing columns are filled with blanks.
    Identifier-like fields are normalized to plain string form.
    """
    out = df.copy()

    for col in required_columns:
        if col not in out.columns:
            out[col] = ""

    for col in out.columns:
        out[col] = out[col].map(normalize_text)

    for col in ID_LIKE_COLUMNS.intersection(out.columns):
        out[col] = out[col].map(normalize_id_like)

    return out[list(required_columns)]


def sort_for_deterministic_export(
    df: pd.DataFrame, key_columns: Sequence[str]
) -> pd.DataFrame:
    existing = [c for c in key_columns if c in df.columns]
    if not existing:
        return df.reset_index(drop=True)
    return df.sort_values(by=existing, kind="stable").reset_index(drop=True)


def csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        return sum(1 for _ in reader)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_csv(path, index=False, encoding="utf-8")


def sql_literal(value: Any) -> str:
    text = normalize_text(value)
    if text == "":
        return "NULL"
    escaped = text.replace("'", "''")
    return f"'{escaped}'"


def sql_insert_statement(
    table_name: str, columns: Sequence[str], rows: Iterable[Dict[str, Any]]
) -> str:
    cols_sql = ", ".join(columns)
    values_sql: List[str] = []
    for row in rows:
        vals = ", ".join(sql_literal(row.get(col, "")) for col in columns)
        values_sql.append(f"({vals})")
    if not values_sql:
        return f"-- No rows to insert into {table_name}\n"
    return (
        f"INSERT INTO {table_name} ({cols_sql}) VALUES\n"
        + ",\n".join(values_sql)
        + "\nON CONFLICT DO NOTHING;\n"
    )


def write_sql(
    df: pd.DataFrame, table_name: str, columns: Sequence[str], path: Path
) -> None:
    rows = df[columns].to_dict(orient="records")
    sql = sql_insert_statement(table_name=table_name, columns=columns, rows=rows)
    ensure_dir(path.parent)
    path.write_text(sql, encoding="utf-8")


def build_manifest(
    input_dir: Path,
    plants_input_path: Path,
    aliases_input_path: Path,
    plants_output_path: Optional[Path],
    aliases_output_path: Optional[Path],
    plants_rows: int,
    aliases_rows: int,
    dry_run: bool,
    emit_sql: bool,
    plants_sql_path: Optional[Path],
    aliases_sql_path: Optional[Path],
) -> Dict[str, Any]:
    return {
        "generated_at": now_utc_iso(),
        "dry_run": dry_run,
        "emit_sql": emit_sql,
        "input_dir": str(input_dir),
        "sources": {
            "plants_input": str(plants_input_path),
            "plant_aliases_input": str(aliases_input_path),
        },
        "outputs": {
            "plants_csv": str(plants_output_path) if plants_output_path else "",
            "plant_aliases_csv": (
                str(aliases_output_path) if aliases_output_path else ""
            ),
            "plants_sql": str(plants_sql_path) if plants_sql_path else "",
            "plant_aliases_sql": str(aliases_sql_path) if aliases_sql_path else "",
        },
        "row_counts": {
            "plants_input_rows": plants_rows,
            "aliases_input_rows": aliases_rows,
            "plants_output_rows": plants_rows,
            "aliases_output_rows": aliases_rows,
        },
        "schema": {
            "plants_columns": list(PLANTS_SCHEMA_COLUMNS),
            "plant_aliases_columns": list(ALIASES_SCHEMA_COLUMNS),
        },
        "status": "planned" if dry_run else "written",
    }


def export_seed_files(
    input_dir: Path,
    output_dir: Path,
    plants_file: str,
    aliases_file: str,
    manifest_file: str,
    emit_sql: bool,
    dry_run: bool,
    plants_sql_file: str,
    aliases_sql_file: str,
) -> ExportResult:
    plants_input_path = input_dir / plants_file
    aliases_input_path = input_dir / aliases_file

    logging.info("Reading validated plants input: %s", plants_input_path)
    plants_df_raw = read_csv(plants_input_path)

    logging.info("Reading validated aliases input: %s", aliases_input_path)
    aliases_df_raw = read_csv(aliases_input_path)

    ensure_required_columns(plants_df_raw, PLANTS_SCHEMA_COLUMNS, "plants.csv")
    ensure_required_columns(aliases_df_raw, ALIASES_SCHEMA_COLUMNS, "plant_aliases.csv")

    plants_df = canonicalize_df(plants_df_raw, PLANTS_SCHEMA_COLUMNS)
    aliases_df = canonicalize_df(aliases_df_raw, ALIASES_SCHEMA_COLUMNS)

    plants_df = sort_for_deterministic_export(plants_df, ["canonical_key", "plant_id"])
    aliases_df = sort_for_deterministic_export(
        aliases_df, ["plant_id", "alias_type", "alias_key", "alias_id"]
    )

    plants_output_path = output_dir / plants_file
    aliases_output_path = output_dir / aliases_file
    manifest_path = output_dir / manifest_file
    plants_sql_path = (output_dir / plants_sql_file) if emit_sql else None
    aliases_sql_path = (output_dir / aliases_sql_file) if emit_sql else None

    if dry_run:
        logging.info("Dry-run enabled; no files will be written.")
        manifest = build_manifest(
            input_dir=input_dir,
            plants_input_path=plants_input_path,
            aliases_input_path=aliases_input_path,
            plants_output_path=plants_output_path,
            aliases_output_path=aliases_output_path,
            plants_rows=len(plants_df),
            aliases_rows=len(aliases_df),
            dry_run=True,
            emit_sql=emit_sql,
            plants_sql_path=plants_sql_path,
            aliases_sql_path=aliases_sql_path,
        )
        logging.info(
            "Planned export: plants_rows=%d aliases_rows=%d",
            len(plants_df),
            len(aliases_df),
        )
        logging.info("Manifest would be written to: %s", manifest_path)
        return ExportResult(
            plants_input_rows=len(plants_df_raw),
            aliases_input_rows=len(aliases_df_raw),
            plants_output_rows=len(plants_df),
            aliases_output_rows=len(aliases_df),
            output_dir=output_dir,
            plants_path=plants_output_path,
            aliases_path=aliases_output_path,
            manifest_path=manifest_path,
            log_path=Path(),
            plants_sql_path=plants_sql_path,
            aliases_sql_path=aliases_sql_path,
        )

    ensure_dir(output_dir)

    logging.info("Writing export plants CSV: %s", plants_output_path)
    write_csv(plants_df, plants_output_path)

    logging.info("Writing export aliases CSV: %s", aliases_output_path)
    write_csv(aliases_df, aliases_output_path)

    if emit_sql:
        assert plants_sql_path is not None
        assert aliases_sql_path is not None
        logging.info("Writing SQL export for plants: %s", plants_sql_path)
        write_sql(plants_df, "plants", PLANTS_SCHEMA_COLUMNS, plants_sql_path)
        logging.info("Writing SQL export for plant_aliases: %s", aliases_sql_path)
        write_sql(aliases_df, "plant_aliases", ALIASES_SCHEMA_COLUMNS, aliases_sql_path)

    manifest = build_manifest(
        input_dir=input_dir,
        plants_input_path=plants_input_path,
        aliases_input_path=aliases_input_path,
        plants_output_path=plants_output_path,
        aliases_output_path=aliases_output_path,
        plants_rows=len(plants_df),
        aliases_rows=len(aliases_df),
        dry_run=False,
        emit_sql=emit_sql,
        plants_sql_path=plants_sql_path,
        aliases_sql_path=aliases_sql_path,
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    logging.info("Writing manifest: %s", manifest_path)

    return ExportResult(
        plants_input_rows=len(plants_df_raw),
        aliases_input_rows=len(aliases_df_raw),
        plants_output_rows=len(plants_df),
        aliases_output_rows=len(aliases_df),
        output_dir=output_dir,
        plants_path=plants_output_path,
        aliases_path=aliases_output_path,
        manifest_path=manifest_path,
        log_path=Path(),
        plants_sql_path=plants_sql_path,
        aliases_sql_path=aliases_sql_path,
    )


def main() -> int:
    args = parse_args()
    cfg = load_settings("plants")
    ensure_dir(args.output_dir)
    log = shared_setup_logging("plants.06_export", cfg)

    log.info("Starting 06_export")
    log.info("Log file: %s", args.output_dir / args.log_file)

    try:
        result = export_seed_files(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            plants_file=args.plants_file,
            aliases_file=args.aliases_file,
            manifest_file=args.manifest_file,
            emit_sql=args.emit_sql,
            dry_run=args.dry_run,
            plants_sql_file=args.plants_sql_file,
            aliases_sql_file=args.aliases_sql_file,
        )

        if args.dry_run:
            log.info(
                "Dry-run complete. plants_rows=%d aliases_rows=%d",
                result.plants_output_rows,
                result.aliases_output_rows,
            )
        else:
            log.info(
                "Export complete. plants_rows=%d aliases_rows=%d",
                result.plants_output_rows,
                result.aliases_output_rows,
            )
        return 0
    except Exception as exc:
        logging.exception("Export failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
