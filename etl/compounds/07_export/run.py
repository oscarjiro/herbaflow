"""Export validated compound ETL outputs into import-ready files for PostgreSQL/Supabase.

Purpose
-------
This is the final delivery step of the compound ETL pipeline. It takes the validated
pass-through outputs from `06_validate`, packages them into stable export files, and
optionally emits SQL or COPY scripts for PostgreSQL/Supabase loading.

Inputs
------
Default inputs come from `compounds/06_validate/out/`:
- validated_compounds.csv
- validated_compound_aliases.csv
- validated_compound_candidate_map.csv
- validated_plant_compounds.csv
- validated_compound_review.csv
- validated_plant_compound_review.csv
- validation_report.json
- validation_counts.csv or validation_summary.csv

Outputs
-------
Written only to `compounds/07_export/out/`:
- compounds.csv
- compound_aliases.csv
- compound_candidate_map.csv
- plant_compounds.csv
- optional audit exports:
  - compound_review.csv
  - plant_compound_review.csv
  - validation_report.json
  - validation_counts.csv
- optional SQL/COPY scripts if enabled in settings
- export_manifest.json
- log file in `out/logs/`

Behavior
--------
- Does not re-validate.
- Does not re-canonicalize.
- Does not enrich.
- Does not mutate the validated source tables.
- Preserves stable ordering and stable column layouts.
- Generates import-ready outputs and an export manifest.
- Optionally generates PostgreSQL/Supabase-compatible SQL or COPY scripts.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required to run this script.") from exc


COMPOUNDS_COLUMNS = [
    "compound_id",
    "canonical_key",
    "canonical_name",
    "inchi_key",
    "smiles",
    "cas_id",
    "pubchem_cid",
    "chembl_id",
    "molecular_formula",
    "molecular_weight",
    "tpsa",
    "logp",
    "hbond_donors",
    "hbond_acceptors",
    "rotatable_bonds",
    "qed_score",
    "np_likeness_score",
    "num_ro5_violations",
    "source_name",
    "source_url",
    "retrieved_at",
    "canonical_status",
    "canonical_strategy",
    "canonical_reason",
    "evidence_count",
    "plant_count",
    "is_pains_positive",
]

ALIASES_COLUMNS = [
    "compound_alias_id",
    "compound_id",
    "alias_name",
    "alias_key",
    "alias_type",
    "retrieved_at",
]

CANDIDATE_MAP_COLUMNS = [
    "compound_candidate_map_id",
    "compound_candidate_id",
    "compound_id",
    "canonical_key",
    "canonical_status",
    "candidate_status",
    "enrichment_status",
    "decision_reason",
    "confidence",
    "source_name",
    "source_batch_id",
    "retrieved_at",
]

PLANT_COMPOUNDS_COLUMNS = [
    "plant_compound_id",
    "plant_id",
    "compound_id",
    "source_name",
    "source_url",
    "retrieved_at",
]

COMPOUND_REVIEW_COLUMNS = [
    "compound_review_id",
    "compound_candidate_id",
    "compound_id",
    "candidate_key",
    "candidate_status",
    "enrichment_status",
    "canonical_status",
    "canonical_strategy",
    "canonical_reason",
    "representative_name",
    "representative_cas_id",
    "representative_formula",
    "representative_mw",
    "pubchem_cid",
    "chembl_id",
    "inchi_key",
    "smiles",
    "molecular_formula",
    "molecular_weight",
    "plant_id",
    "canonical_plant_id",
    "source_compound_key",
    "source_plant_raw_id",
    "source_name",
    "source_batch_id",
    "retrieved_at",
    "issue_type",
    "issue_reason",
    "evidence_summary_json",
]

PLANT_REVIEW_COLUMNS = [
    "plant_compound_review_id",
    "compound_candidate_id",
    "compound_id",
    "canonical_key",
    "candidate_status",
    "enrichment_status",
    "plant_id",
    "canonical_plant_id",
    "source_compound_key",
    "source_plant_raw_id",
    "source_name",
    "source_batch_id",
    "retrieved_at",
    "issue_type",
    "issue_reason",
    "evidence_summary_json",
]

VALIDATION_REQUIRED_EXPORTS = [
    "validation_report.json",
    "validation_counts.csv",
]


@dataclass(frozen=True)
class Settings:
    module_root: Path
    project_root: Path
    validate_out_dir: Path
    export_out_dir: Path
    export_log_dir: Path
    sql_enabled: bool
    sql_mode: str  # insert | copy
    sql_schema: str
    sql_include_audit_tables: bool
    sql_quote_identifiers: bool
    overwrite_outputs: bool
    run_id_prefix: str
    timestamp_format: str
    batch_id: str
    include_audit_exports: bool
    include_validation_artifacts: bool


def normalize_whitespace(value: Optional[str]) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def parse_float(value: Optional[str]) -> Optional[float]:
    text = normalize_whitespace(value)
    if not text:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def stable_run_id(settings: Settings) -> str:
    if settings.batch_id and settings.batch_id != "auto":
        return f"{settings.run_id_prefix}_{settings.batch_id}"
    return f"{settings.run_id_prefix}_{datetime.now(timezone.utc).strftime(settings.timestamp_format)}"


def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configure_logging(log_dir: Path, run_id: str) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"export_compounds_{run_id}.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root.addHandler(stream_handler)
    root.addHandler(file_handler)
    return log_path


def resolve_rel(base: Path, value: Optional[str], default: str) -> Path:
    raw = value or default
    p = Path(raw)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def load_settings(settings_path: Path) -> Settings:
    with settings_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    module_root = settings_path.parent.resolve()
    project_root = (module_root / config["project"]["project_root"]).resolve()

    def resolve_project_rel(value: str) -> Path:
        p = Path(value)
        if p.is_absolute():
            return p
        return (project_root / p).resolve()

    paths_cfg = config.get("paths", {})
    step_dirs_cfg = paths_cfg.get("step_dirs", {})
    logs_cfg = paths_cfg.get("logs", {})
    batch_cfg = config.get("batch", {})
    runtime_cfg = config.get("runtime", {})
    sql_cfg = config.get("sql_export", {})
    export_cfg = config.get("export", {})

    validate_out_dir = resolve_project_rel(
        step_dirs_cfg.get("validate_out", "compounds/06_validate/out")
    )
    export_out_dir = resolve_project_rel(
        step_dirs_cfg.get("export_out", "compounds/07_export/out")
    )
    export_log_dir = resolve_project_rel(
        logs_cfg.get("export", "compounds/07_export/out/logs")
    )

    return Settings(
        module_root=module_root,
        project_root=project_root,
        validate_out_dir=validate_out_dir,
        export_out_dir=export_out_dir,
        export_log_dir=export_log_dir,
        sql_enabled=bool(sql_cfg.get("enabled", False)),
        sql_mode=str(sql_cfg.get("mode", "insert")).strip().lower(),
        sql_schema=str(sql_cfg.get("schema", "public")),
        sql_include_audit_tables=bool(sql_cfg.get("include_audit_tables", False)),
        sql_quote_identifiers=bool(sql_cfg.get("quote_identifiers", False)),
        overwrite_outputs=bool(batch_cfg.get("overwrite_outputs", False)),
        run_id_prefix=str(batch_cfg.get("run_id_prefix", "compounds")),
        timestamp_format=str(batch_cfg.get("timestamp_format", "%Y%m%d_%H%M%S")),
        batch_id=str(batch_cfg.get("batch_id", "auto")),
        include_audit_exports=bool(export_cfg.get("include_audit_exports", True)),
        include_validation_artifacts=bool(
            export_cfg.get("include_validation_artifacts", True)
        ),
    )


def ensure_columns(
    fieldnames: Sequence[str], required: Sequence[str], label: str
) -> None:
    missing = [c for c in required if c not in fieldnames]
    if missing:
        raise ValueError(f"{label} is missing expected columns: {missing}")


def read_csv_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"File has no header row: {path}")
        rows = list(reader)
        return rows, list(reader.fieldnames)


def write_csv(
    path: Path, rows: List[Dict[str, Any]], fieldnames: Sequence[str], overwrite: bool
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Dict[str, Any], overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def stable_sort(
    rows: List[Dict[str, str]], key_fields: Sequence[str]
) -> List[Dict[str, str]]:
    if not rows:
        return rows
    return sorted(
        rows,
        key=lambda r: tuple(normalize_whitespace(r.get(k, "")) for k in key_fields),
    )


def load_validated_table(
    path: Path, required_columns: Sequence[str], label: str
) -> Tuple[List[Dict[str, str]], List[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required validated input: {path}")
    rows, fields = read_csv_rows(path)
    ensure_columns(fields, required_columns, label)
    return rows, fields


def load_optional_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, dict) else None


def load_validation_counts(path: Path) -> Optional[List[Dict[str, str]]]:
    if not path.exists():
        return None
    rows, _fields = read_csv_rows(path)
    return rows


def sql_quote_identifier(name: str, quote: bool) -> str:
    if not quote:
        return name
    return '"' + name.replace('"', '""') + '"'


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return "NULL"
        return str(value)
    text = str(value)
    if text == "":
        return "NULL"
    return "'" + text.replace("'", "''") + "'"


def csv_row_to_sql_values(row: Dict[str, Any], fieldnames: Sequence[str]) -> List[str]:
    values: List[str] = []
    for f in fieldnames:
        val = row.get(f, "")
        if val is None:
            values.append("")
        else:
            values.append(str(val))
    return values


def generate_insert_sql(
    table_name: str,
    fieldnames: Sequence[str],
    rows: List[Dict[str, Any]],
    schema: str,
    quote_identifiers: bool,
) -> str:
    qualified_table = f"{sql_quote_identifier(schema, quote_identifiers)}.{sql_quote_identifier(table_name, quote_identifiers)}"
    cols = ", ".join(sql_quote_identifier(c, quote_identifiers) for c in fieldnames)
    statements = [f"INSERT INTO {qualified_table} ({cols}) VALUES"]
    if not rows:
        statements.append("  DEFAULT VALUES;")
        return "\n".join(statements)

    values_sql = []
    for row in rows:
        vals = ", ".join(sql_literal(row.get(f)) for f in fieldnames)
        values_sql.append(f"  ({vals})")
    statements.append(",\n".join(values_sql) + ";")
    return "\n".join(statements)


def generate_copy_sql(
    table_name: str,
    fieldnames: Sequence[str],
    rows: List[Dict[str, Any]],
    schema: str,
    quote_identifiers: bool,
) -> str:
    qualified_table = f"{sql_quote_identifier(schema, quote_identifiers)}.{sql_quote_identifier(table_name, quote_identifiers)}"
    cols = ", ".join(sql_quote_identifier(c, quote_identifiers) for c in fieldnames)
    out_lines = [
        f"COPY {qualified_table} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true);"
    ]
    buffer = []
    if rows:
        import io

        sio = io.StringIO()
        writer = csv.DictWriter(sio, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        buffer = sio.getvalue().splitlines()
        out_lines.extend(
            buffer[1:]
        )  # skip header in data block; COPY header already declared
    out_lines.append("\\.")
    return "\n".join(out_lines) + "\n"


def write_sql_file(
    path: Path,
    table_name: str,
    fieldnames: Sequence[str],
    rows: List[Dict[str, Any]],
    settings: Settings,
    overwrite: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    if settings.sql_mode == "copy":
        sql = generate_copy_sql(
            table_name,
            fieldnames,
            rows,
            settings.sql_schema,
            settings.sql_quote_identifiers,
        )
    else:
        sql = generate_insert_sql(
            table_name,
            fieldnames,
            rows,
            settings.sql_schema,
            settings.sql_quote_identifiers,
        )

    with path.open("w", encoding="utf-8") as f:
        f.write(f"-- Export generated at {timestamp_now()}\n")
        f.write(f"-- Table: {table_name}\n")
        f.write(sql)
        if not sql.endswith("\n"):
            f.write("\n")


def export_row_count(rows: List[Dict[str, Any]]) -> int:
    return len(rows)


def copy_json_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8")
    dst.write_text(text, encoding="utf-8")


def copy_csv_file_as_table(
    rows: List[Dict[str, str]],
    fieldnames: Sequence[str],
    dst: Path,
    overwrite: bool,
) -> None:
    write_csv(dst, rows, fieldnames, overwrite=overwrite)


def core_export_bundle(
    settings: Settings,
    logger: logging.Logger,
) -> Dict[str, Any]:
    validate_dir = settings.validate_out_dir

    compounds_rows, compounds_fields = load_validated_table(
        validate_dir / "validated_compounds.csv",
        COMPOUNDS_COLUMNS,
        "validated_compounds.csv",
    )
    aliases_rows, aliases_fields = load_validated_table(
        validate_dir / "validated_compound_aliases.csv",
        ALIASES_COLUMNS,
        "validated_compound_aliases.csv",
    )
    candidate_map_rows, candidate_map_fields = load_validated_table(
        validate_dir / "validated_compound_candidate_map.csv",
        CANDIDATE_MAP_COLUMNS,
        "validated_compound_candidate_map.csv",
    )
    plant_rows, plant_fields = load_validated_table(
        validate_dir / "validated_plant_compounds.csv",
        PLANT_COMPOUNDS_COLUMNS,
        "validated_plant_compounds.csv",
    )
    compound_review_rows, compound_review_fields = load_validated_table(
        validate_dir / "validated_compound_review.csv",
        COMPOUND_REVIEW_COLUMNS,
        "validated_compound_review.csv",
    )
    plant_review_rows, plant_review_fields = load_validated_table(
        validate_dir / "validated_plant_compound_review.csv",
        PLANT_REVIEW_COLUMNS,
        "validated_plant_compound_review.csv",
    )

    validation_report_path = validate_dir / "validation_report.json"
    validation_counts_path = validate_dir / "validation_counts.csv"
    if not validation_counts_path.exists():
        alt = validate_dir / "validation_summary.csv"
        if alt.exists():
            validation_counts_path = alt

    validation_report = load_optional_json(validation_report_path)
    validation_counts = load_validation_counts(validation_counts_path)

    compounds_rows = stable_sort(compounds_rows, ["compound_id", "canonical_key"])
    aliases_rows = stable_sort(aliases_rows, ["compound_id", "alias_key", "alias_type"])
    candidate_map_rows = stable_sort(candidate_map_rows, ["compound_candidate_id"])
    plant_rows = stable_sort(plant_rows, ["plant_id", "compound_id"])
    compound_review_rows = stable_sort(compound_review_rows, ["compound_review_id"])
    plant_review_rows = stable_sort(plant_review_rows, ["plant_compound_review_id"])

    if not compounds_rows:
        logger.warning("validated_compounds.csv is empty")
    if not aliases_rows:
        logger.warning("validated_compound_aliases.csv is empty")
    if not candidate_map_rows:
        logger.warning("validated_compound_candidate_map.csv is empty")
    if not plant_rows:
        logger.warning("validated_plant_compounds.csv is empty")

    out = settings.export_out_dir
    out.mkdir(parents=True, exist_ok=True)

    core_files = {
        "compounds.csv": (compounds_rows, COMPOUNDS_COLUMNS),
        "compound_aliases.csv": (aliases_rows, ALIASES_COLUMNS),
        "compound_candidate_map.csv": (candidate_map_rows, CANDIDATE_MAP_COLUMNS),
        "plant_compounds.csv": (plant_rows, PLANT_COMPOUNDS_COLUMNS),
    }

    audit_files = {}
    if settings.include_audit_exports:
        audit_files = {
            "compound_review.csv": (compound_review_rows, COMPOUND_REVIEW_COLUMNS),
            "plant_compound_review.csv": (plant_review_rows, PLANT_REVIEW_COLUMNS),
        }

    exported_files: Dict[str, Dict[str, Any]] = {}

    for filename, (rows, fields) in core_files.items():
        dst = out / filename
        copy_csv_file_as_table(rows, fields, dst, overwrite=settings.overwrite_outputs)
        exported_files[filename] = {
            "path": str(dst),
            "row_count": len(rows),
            "columns": list(fields),
            "kind": "core",
        }

    if settings.include_audit_exports:
        for filename, (rows, fields) in audit_files.items():
            dst = out / filename
            copy_csv_file_as_table(
                rows, fields, dst, overwrite=settings.overwrite_outputs
            )
            exported_files[filename] = {
                "path": str(dst),
                "row_count": len(rows),
                "columns": list(fields),
                "kind": "audit",
            }

    if settings.include_validation_artifacts:
        if validation_report is not None:
            dst = out / "validation_report.json"
            copy_json_file(validation_report_path, dst)
            exported_files["validation_report.json"] = {
                "path": str(dst),
                "row_count": 1,
                "columns": [],
                "kind": "validation_artifact",
            }
        if validation_counts is not None:
            dst = out / "validation_counts.csv"
            copy_csv_file_as_table(
                validation_counts,
                list(validation_counts[0].keys()) if validation_counts else [],
                dst,
                overwrite=settings.overwrite_outputs,
            )
            exported_files["validation_counts.csv"] = {
                "path": str(dst),
                "row_count": len(validation_counts),
                "columns": (
                    list(validation_counts[0].keys()) if validation_counts else []
                ),
                "kind": "validation_artifact",
            }

    sql_files = {}
    if settings.sql_enabled:
        sql_order = [
            ("compounds.sql", "compounds", compounds_rows, COMPOUNDS_COLUMNS),
            (
                "compound_candidate_map.sql",
                "compound_candidate_map",
                candidate_map_rows,
                CANDIDATE_MAP_COLUMNS,
            ),
            ("compound_aliases.sql", "compound_aliases", aliases_rows, ALIASES_COLUMNS),
            (
                "plant_compounds.sql",
                "plant_compounds",
                plant_rows,
                PLANT_COMPOUNDS_COLUMNS,
            ),
        ]
        if settings.sql_include_audit_tables and settings.include_audit_exports:
            sql_order.extend(
                [
                    (
                        "compound_review.sql",
                        "compound_review",
                        compound_review_rows,
                        COMPOUND_REVIEW_COLUMNS,
                    ),
                    (
                        "plant_compound_review.sql",
                        "plant_compound_review",
                        plant_review_rows,
                        PLANT_REVIEW_COLUMNS,
                    ),
                ]
            )

        for filename, table_name, rows, fields in sql_order:
            dst = out / filename
            write_sql_file(
                dst,
                table_name,
                fields,
                rows,
                settings,
                overwrite=settings.overwrite_outputs,
            )
            sql_files[filename] = {
                "path": str(dst),
                "row_count": len(rows),
                "columns": list(fields),
                "kind": "sql",
            }

    manifest = {
        "module": "compounds",
        "step": "07_export",
        "run_id": stable_run_id(settings),
        "generated_at": timestamp_now(),
        "settings_file": str(settings.module_root / "settings.yml"),
        "source_validated_dir": str(validate_dir),
        "sql_enabled": settings.sql_enabled,
        "sql_mode": settings.sql_mode,
        "sql_schema": settings.sql_schema,
        "sql_include_audit_tables": settings.sql_include_audit_tables,
        "include_audit_exports": settings.include_audit_exports,
        "include_validation_artifacts": settings.include_validation_artifacts,
        "files": {**exported_files, **sql_files},
        "summary": {
            "compounds_row_count": len(compounds_rows),
            "compound_aliases_row_count": len(aliases_rows),
            "compound_candidate_map_row_count": len(candidate_map_rows),
            "plant_compounds_row_count": len(plant_rows),
            "compound_review_row_count": len(compound_review_rows),
            "plant_compound_review_row_count": len(plant_review_rows),
            "validation_report_present": validation_report is not None,
            "validation_counts_present": validation_counts is not None,
        },
        "note": "export_pass_through_only",
    }

    return {
        "manifest": manifest,
        "compound_review_rows": compound_review_rows,
        "plant_review_rows": plant_review_rows,
        "validation_report_path": validation_report_path,
        "validation_counts_path": validation_counts_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export validated compound ETL outputs."
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "settings.yml"),
        help="Path to the compound ETL settings.yml file.",
    )
    args = parser.parse_args()

    settings_path = Path(args.settings).resolve()
    settings = load_settings(settings_path)
    run_id = stable_run_id(settings)
    log_path = configure_logging(settings.export_log_dir, run_id)
    logger = logging.getLogger("compounds.export")

    logger.info("Starting export run_id=%s", run_id)
    logger.info("Settings path: %s", settings_path)
    logger.info("Validated input dir: %s", settings.validate_out_dir)
    logger.info("Export output dir: %s", settings.export_out_dir)

    required_inputs = [
        settings.validate_out_dir / "validated_compounds.csv",
        settings.validate_out_dir / "validated_compound_aliases.csv",
        settings.validate_out_dir / "validated_compound_candidate_map.csv",
        settings.validate_out_dir / "validated_plant_compounds.csv",
        settings.validate_out_dir / "validated_compound_review.csv",
        settings.validate_out_dir / "validated_plant_compound_review.csv",
        settings.validate_out_dir / "validation_report.json",
    ]
    for path in required_inputs:
        if not path.exists():
            raise FileNotFoundError(f"Required validated input missing: {path}")

    bundle = core_export_bundle(settings, logger)
    manifest = bundle["manifest"]

    manifest_path = settings.export_out_dir / "export_manifest.json"
    write_json(manifest_path, manifest, overwrite=settings.overwrite_outputs)

    logger.info("Exported files:")
    for name, meta in sorted(manifest["files"].items()):
        logger.info(
            "  %s | rows=%s | %s", name, meta.get("row_count"), meta.get("path")
        )

    logger.info("Manifest: %s", manifest_path)
    logger.info("Log file: %s", log_path)
    logger.info("Completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
