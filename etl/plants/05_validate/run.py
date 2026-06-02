"""
05_validate: validate final canonical plant seed files before export.

Inputs:
    04_build_canonical/out/plants.csv
    04_build_canonical/out/plant_aliases.csv

Outputs:
    05_validate/out/plants.csv
    05_validate/out/plant_aliases.csv
    05_validate/out/validation_report.csv
    05_validate/out/validation_report.json
    05_validate/out/validate.log

Validation checks:
- duplicate canonical plants
- duplicate aliases
- missing required columns
- orphan aliases that do not point to a valid plant_id
- empty or suspicious canonical names
- source_name values that incorrectly contain plant names instead of source system names

Behavior:
- writes validated pass-through seed files when inputs are structurally valid
- preserves import-ready IDs and schema-aligned column order
- exits nonzero if any critical validation failures are found

Run:
    python validate_seed_files.py \
        --plants 04_build_canonical/out/plants.csv \
        --aliases 04_build_canonical/out/plant_aliases.csv \
        --output-dir 05_validate/out
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


def _defaults() -> dict:
    cfg = load_settings("plants")
    return cfg["paths"]["validate"]

REQUIRED_PLANT_COLUMNS = [
    "plant_id",
    "raw_plant_id",
    "canonical_key",
    "canonical_scientific_name",
    "family_name",
    "source_name",
    "source_url",
    "retrieved_at",
]

REQUIRED_ALIAS_COLUMNS = [
    "alias_id",
    "plant_id",
    "alias_name",
    "alias_key",
    "alias_type",
    "retrieved_at",
]

ALLOWED_ALIAS_TYPES = {
    "exact_scraped_spelling",
    "synonym_variant",
    "author_variant",
    "normalized_variant",
}

PLANT_OUTPUT_COLUMNS = REQUIRED_PLANT_COLUMNS
ALIAS_OUTPUT_COLUMNS = REQUIRED_ALIAS_COLUMNS

WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class Issue:
    severity: str  # critical | warning
    check_name: str
    table_name: str
    row_index: Optional[int]
    plant_id: str
    alias_id: str
    column_name: str
    value: str
    details: str


def parse_args() -> argparse.Namespace:
    step = _defaults()
    parser = argparse.ArgumentParser(
        description="Validate final canonical plant seed files before export."
    )
    parser.add_argument(
        "--plants",
        type=Path,
        default=ETL_ROOT / step["plants"],
        help="Path to plants.csv (default: plants/04_build_canonical/out/plants.csv)",
    )
    parser.add_argument(
        "--aliases",
        type=Path,
        default=ETL_ROOT / step["aliases"],
        help="Path to plant_aliases.csv (default: plants/04_build_canonical/out/plant_aliases.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ETL_ROOT / step["output_dir"],
        help="Directory where validation outputs will be written (default: plants/05_validate/out)",
    )
    parser.add_argument(
        "--report-csv",
        type=str,
        default=step["report_csv"],
        help="Filename for validation report CSV (default: validation_report.csv)",
    )
    parser.add_argument(
        "--report-json",
        type=str,
        default=step["report_json"],
        help="Filename for validation report JSON (default: validation_report.json)",
    )
    parser.add_argument(
        "--validated-plants",
        type=str,
        default=step["validated_plants"],
        help="Filename for validated plants CSV (default: plants.csv)",
    )
    parser.add_argument(
        "--validated-aliases",
        type=str,
        default=step["validated_aliases"],
        help="Filename for validated aliases CSV (default: plant_aliases.csv)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=step["log_file"],
        help="Filename for the validation log (default: validate.log)",
    )
    return parser.parse_args()



def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def is_empty_canonical_name(name: Any) -> bool:
    return normalize_text(name) == ""


def is_suspicious_canonical_name(name: Any) -> bool:
    text = normalize_text(name)
    if not text:
        return True
    if len(text) < 3:
        return True
    if any(ch.isdigit() for ch in text):
        return True
    if re.search(r"[,;】【：!/]", text):
        return True
    tokens = text.split()
    if len(tokens) < 2:
        return True
    return False


def source_name_looks_like_plant_name(
    source_name: Any, canonical_names: set[str], alias_names: set[str]
) -> bool:
    text = normalize_text(source_name)
    if not text:
        return True

    folded = text.lower()
    if folded in canonical_names or folded in alias_names:
        return True

    if re.match(r"^[A-Z][a-zA-Z-]+(?:\s+[a-z][a-zA-Z-]+){1,3}$", text):
        return True

    source_keywords = {
        "world",
        "knapsack",
        "gbif",
        "supabase",
        "thesis",
        "database",
        "dataset",
    }
    if any(k in folded for k in source_keywords):
        return False

    if re.search(r"(\bsp\.\b)|(\bcf\.\b)|(\baff\.\b)", text, flags=re.IGNORECASE):
        return True

    return False


def add_issue(
    issues: List[Issue],
    severity: str,
    check_name: str,
    table_name: str,
    row_index: Optional[int],
    plant_id: Any = "",
    alias_id: Any = "",
    column_name: str = "",
    value: Any = "",
    details: str = "",
) -> None:
    issues.append(
        Issue(
            severity=severity,
            check_name=check_name,
            table_name=table_name,
            row_index=row_index,
            plant_id=normalize_text(plant_id),
            alias_id=normalize_text(alias_id),
            column_name=column_name,
            value=normalize_text(value),
            details=details,
        )
    )


def missing_columns(
    table_name: str, df: pd.DataFrame, required: Sequence[str], issues: List[Issue]
) -> List[str]:
    present = set(df.columns)
    missing = [c for c in required if c not in present]
    if missing:
        add_issue(
            issues,
            severity="critical",
            check_name="missing_required_columns",
            table_name=table_name,
            row_index=None,
            details=f"Missing required columns: {', '.join(missing)}",
        )
    return missing


def find_duplicate_rows(
    df: pd.DataFrame,
    subset: Sequence[str],
    table_name: str,
    check_name: str,
    issues: List[Issue],
    severity: str = "critical",
) -> int:
    cols = [c for c in subset if c in df.columns]
    if not cols:
        return 0

    dup_mask = df.duplicated(subset=cols, keep=False)
    dup_count = int(dup_mask.sum())
    if dup_count:
        for idx, row in df.loc[dup_mask].iterrows():
            add_issue(
                issues,
                severity=severity,
                check_name=check_name,
                table_name=table_name,
                row_index=int(idx),
                plant_id=row.get("plant_id", ""),
                alias_id=row.get("alias_id", ""),
                column_name=",".join(cols),
                value="; ".join(f"{c}={normalize_text(row.get(c, ''))}" for c in cols),
                details="Duplicate row detected for the specified key fields.",
            )
    return dup_count


def prepare_output_frame(
    df: pd.DataFrame, required_columns: Sequence[str]
) -> pd.DataFrame:
    out = df.copy()

    for col in required_columns:
        if col not in out.columns:
            out[col] = ""

    for col in out.columns:
        out[col] = out[col].map(normalize_text)

    out = out[list(required_columns)]
    return out


def validate_plants(df: pd.DataFrame, issues: List[Issue]) -> None:
    missing_columns("plants", df, REQUIRED_PLANT_COLUMNS, issues)

    if "plant_id" in df.columns:
        find_duplicate_rows(
            df,
            subset=["plant_id"],
            table_name="plants",
            check_name="duplicate_canonical_plants_by_plant_id",
            issues=issues,
        )

    if "canonical_key" in df.columns:
        find_duplicate_rows(
            df,
            subset=["canonical_key"],
            table_name="plants",
            check_name="duplicate_canonical_plants_by_canonical_key",
            issues=issues,
        )

    canonical_names = set(
        normalize_text(v).lower()
        for v in df.get("canonical_scientific_name", pd.Series(dtype=str)).tolist()
    )
    alias_names: set[str] = set()

    for idx, row in df.iterrows():
        plant_id = row.get("plant_id", "")
        canonical_name = row.get("canonical_scientific_name", "")
        source_name = row.get("source_name", "")

        if is_empty_canonical_name(canonical_name):
            add_issue(
                issues,
                severity="critical",
                check_name="empty_canonical_name",
                table_name="plants",
                row_index=int(idx),
                plant_id=plant_id,
                column_name="canonical_scientific_name",
                value=canonical_name,
                details="Canonical scientific name is empty.",
            )
        elif is_suspicious_canonical_name(canonical_name):
            add_issue(
                issues,
                severity="warning",
                check_name="suspicious_canonical_name",
                table_name="plants",
                row_index=int(idx),
                plant_id=plant_id,
                column_name="canonical_scientific_name",
                value=canonical_name,
                details="Canonical scientific name looks suspicious or malformed.",
            )

        if source_name_looks_like_plant_name(source_name, canonical_names, alias_names):
            add_issue(
                issues,
                severity="critical",
                check_name="source_name_looks_like_plant_name",
                table_name="plants",
                row_index=int(idx),
                plant_id=plant_id,
                column_name="source_name",
                value=source_name,
                details="source_name appears to contain a plant name rather than a source system name.",
            )


def validate_aliases(
    df: pd.DataFrame, plants_df: pd.DataFrame, issues: List[Issue]
) -> None:
    missing_columns("plant_aliases", df, REQUIRED_ALIAS_COLUMNS, issues)

    if "alias_id" in df.columns:
        find_duplicate_rows(
            df,
            subset=["alias_id"],
            table_name="plant_aliases",
            check_name="duplicate_aliases_by_alias_id",
            issues=issues,
        )

    logical_subset = [
        c
        for c in ["plant_id", "alias_key", "alias_type", "alias_name"]
        if c in df.columns
    ]
    if len(logical_subset) >= 2:
        find_duplicate_rows(
            df,
            subset=logical_subset,
            table_name="plant_aliases",
            check_name="duplicate_aliases_by_logical_key",
            issues=issues,
        )

    valid_plant_ids = set(
        normalize_text(v)
        for v in plants_df.get("plant_id", pd.Series(dtype=str)).tolist()
    )

    for idx, row in df.iterrows():
        alias_id = row.get("alias_id", "")
        plant_id = row.get("plant_id", "")
        alias_name = row.get("alias_name", "")
        alias_type = normalize_text(row.get("alias_type", ""))

        if normalize_text(plant_id) not in valid_plant_ids:
            add_issue(
                issues,
                severity="critical",
                check_name="orphan_alias",
                table_name="plant_aliases",
                row_index=int(idx),
                plant_id=plant_id,
                alias_id=alias_id,
                column_name="plant_id",
                value=plant_id,
                details="Alias plant_id does not reference a valid plant_id in plants.csv.",
            )

        if not normalize_text(alias_name):
            add_issue(
                issues,
                severity="critical",
                check_name="empty_alias_name",
                table_name="plant_aliases",
                row_index=int(idx),
                plant_id=plant_id,
                alias_id=alias_id,
                column_name="alias_name",
                value=alias_name,
                details="Alias name is empty.",
            )

        if alias_type and alias_type not in ALLOWED_ALIAS_TYPES:
            add_issue(
                issues,
                severity="critical",
                check_name="invalid_alias_type",
                table_name="plant_aliases",
                row_index=int(idx),
                plant_id=plant_id,
                alias_id=alias_id,
                column_name="alias_type",
                value=alias_type,
                details=f"Alias type '{alias_type}' is not in the allowed set.",
            )


def issues_to_dataframe(issues: List[Issue]) -> pd.DataFrame:
    rows = [asdict(issue) for issue in issues]
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "severity",
                "check_name",
                "table_name",
                "row_index",
                "plant_id",
                "alias_id",
                "column_name",
                "value",
                "details",
            ]
        )
    return df


def build_report_payload(
    issues: List[Issue],
    plants_df: pd.DataFrame,
    aliases_df: pd.DataFrame,
    plants_input_path: Path,
    aliases_input_path: Path,
    plants_output_path: Path,
    aliases_output_path: Path,
    report_csv_path: Path,
    report_json_path: Path,
) -> Dict[str, Any]:
    critical = sum(1 for i in issues if i.severity == "critical")
    warning = sum(1 for i in issues if i.severity == "warning")

    checks: Dict[str, Dict[str, int]] = {}
    for issue in issues:
        checks.setdefault(issue.check_name, {"critical": 0, "warning": 0, "total": 0})
        checks[issue.check_name][issue.severity] += 1
        checks[issue.check_name]["total"] += 1

    return {
        "generated_at": now_utc_iso(),
        "summary": {
            "critical_issues": critical,
            "warning_issues": warning,
            "total_issues": len(issues),
            "plants_rows": int(len(plants_df)),
            "aliases_rows": int(len(aliases_df)),
            "status": "fail" if critical > 0 else "pass",
        },
        "source_files": {
            "plants": str(plants_input_path),
            "aliases": str(aliases_input_path),
        },
        "output_files": {
            "validated_plants": str(plants_output_path),
            "validated_aliases": str(aliases_output_path),
            "report_csv": str(report_csv_path),
            "report_json": str(report_json_path),
        },
        "checks": checks,
    }


def write_validated_outputs(
    plants_df: pd.DataFrame,
    aliases_df: pd.DataFrame,
    output_dir: Path,
    validated_plants_name: str,
    validated_aliases_name: str,
) -> Tuple[Path, Path]:
    ensure_dir(output_dir)
    plants_path = output_dir / validated_plants_name
    aliases_path = output_dir / validated_aliases_name

    plants_out = prepare_output_frame(plants_df, PLANT_OUTPUT_COLUMNS)
    aliases_out = prepare_output_frame(aliases_df, ALIAS_OUTPUT_COLUMNS)

    plants_out = plants_out.sort_values(
        by=["canonical_key", "plant_id"], kind="stable"
    ).reset_index(drop=True)
    aliases_out = aliases_out.sort_values(
        by=["plant_id", "alias_type", "alias_key", "alias_id"], kind="stable"
    ).reset_index(drop=True)

    plants_out.to_csv(plants_path, index=False, encoding="utf-8")
    aliases_out.to_csv(aliases_path, index=False, encoding="utf-8")

    return plants_path, aliases_path


def write_report_csv(issues: List[Issue], report_csv_path: Path) -> None:
    issues_df = issues_to_dataframe(issues)
    issues_df.to_csv(report_csv_path, index=False, encoding="utf-8")


def write_report_json(payload: Dict[str, Any], report_json_path: Path) -> None:
    with report_json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)


def validate_files(
    plants_path: Path,
    aliases_path: Path,
    output_dir: Path,
    report_csv_name: str,
    report_json_name: str,
    validated_plants_name: str,
    validated_aliases_name: str,
) -> int:
    logging.info("Reading plants file: %s", plants_path)
    plants_df = read_csv(plants_path)

    logging.info("Reading aliases file: %s", aliases_path)
    aliases_df = read_csv(aliases_path)

    issues: List[Issue] = []

    validate_plants(plants_df, issues)
    validate_aliases(aliases_df, plants_df, issues)

    report_csv_path = output_dir / report_csv_name
    report_json_path = output_dir / report_json_name

    payload = build_report_payload(
        issues=issues,
        plants_df=plants_df,
        aliases_df=aliases_df,
        plants_input_path=plants_path,
        aliases_input_path=aliases_path,
        plants_output_path=output_dir / validated_plants_name,
        aliases_output_path=output_dir / validated_aliases_name,
        report_csv_path=report_csv_path,
        report_json_path=report_json_path,
    )

    write_report_csv(issues, report_csv_path)
    write_report_json(payload, report_json_path)

    critical = payload["summary"]["critical_issues"]
    warning = payload["summary"]["warning_issues"]

    # Write validated pass-through outputs when the source files are structurally valid.
    # This keeps 06_export reading from 05_validate/out/ as intended.
    if not any(issue.check_name == "missing_required_columns" for issue in issues):
        validated_plants_path, validated_aliases_path = write_validated_outputs(
            plants_df=plants_df,
            aliases_df=aliases_df,
            output_dir=output_dir,
            validated_plants_name=validated_plants_name,
            validated_aliases_name=validated_aliases_name,
        )
        logging.info("Validated plants written: %s", validated_plants_path)
        logging.info("Validated aliases written: %s", validated_aliases_path)
    else:
        logging.warning(
            "Skipping validated output files because required columns are missing."
        )

    logging.info("Validation report CSV written: %s", report_csv_path)
    logging.info("Validation report JSON written: %s", report_json_path)
    logging.info(
        "Validation summary: critical=%d warning=%d total=%d status=%s",
        critical,
        warning,
        payload["summary"]["total_issues"],
        "FAIL" if critical > 0 else "PASS",
    )

    return 1 if critical > 0 else 0


def main() -> int:
    args = parse_args()
    cfg = load_settings("plants")
    ensure_dir(args.output_dir)
    log = shared_setup_logging("plants.05_validate", cfg)

    log.info("Starting 05_validate")
    log.info("Log file: %s", args.output_dir / args.log_file)

    try:
        exit_code = validate_files(
            plants_path=args.plants,
            aliases_path=args.aliases,
            output_dir=args.output_dir,
            report_csv_name=args.report_csv,
            report_json_name=args.report_json,
            validated_plants_name=args.validated_plants,
            validated_aliases_name=args.validated_aliases,
        )
        return exit_code
    except Exception as exc:
        logging.exception("Validation failed unexpectedly: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
