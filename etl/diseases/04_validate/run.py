"""Validation step for the refactored disease ETL pipeline.

Purpose
-------
Validate the canonical disease outputs before export. This step checks
structural correctness, key uniqueness, alias integrity, ontology mapping
quality, and required provenance fields so the thesis pipeline remains
auditable and defensible.

Inputs
------
- diseases/settings.yml for configuration and validation rules
- The previous step output from diseases/03_build_canonical/out/ by default

Outputs
-------
- validation_report.csv: machine-readable issue report
- validation_report.json: summary counts and pass/fail status
- issues.csv: same issue report, kept as a convenience file
- optional run.log summary in diseases/04_validate/out/

Behavior
--------
- Validates canonical disease rows, alias rows, and alias map rows
- Checks duplicate keys, missing IDs, malformed keys, orphan aliases, and
  ontology ID format
- Reports duplicate disease names, suspicious near-duplicates, and unmapped
  diseases
- Preserves source data unchanged and never silently fixes problems
- Fails on critical errors when settings.yml enables stop_on_validation_error
- Is idempotent and safe to rerun from the command line
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir, now_iso

from diseases.utils import (
    normalize_text,
    read_csv,
    safe_str,
    validate_required_columns,
    write_csv,
)

DEFAULT_SETTINGS_PATH = ETL_ROOT / "diseases" / "settings.yml"

CANONICAL_FILE = "diseases.csv"
ALIASES_FILE = "disease_aliases.csv"
ALIAS_MAP_FILE = "disease_alias_map.csv"

CANONICAL_REQUIRED_COLUMNS = (
    "disease_id",
    "disease_key",
    "disease_name",
    "source_id",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
)
ALIAS_REQUIRED_COLUMNS = (
    "alias_id",
    "alias_key",
    "alias_name",
    "disease_id",
    "disease_key",
    "alias_type",
    "source_id",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
)
ALIAS_MAP_REQUIRED_COLUMNS = (
    "alias_map_id",
    "alias",
    "alias_key",
    "disease_key",
    "disease_id",
    "type",
    "source_id",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
)

DISEASE_KEY_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
ONTOLOGY_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?::|_)[A-Za-z0-9]+$")


def _resolve_path(base_dir: Path, raw_value: str, default_value: str) -> Path:
    """Resolve a configured path relative to the project root."""
    path = Path(raw_value or default_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _resolve_paths(settings: dict[str, Any], settings_path: Path) -> tuple[Path, Path]:
    """Resolve canonical input and validation output paths."""
    paths = settings.get("paths", {})
    canonical_out = _resolve_path(
        ETL_ROOT,
        str(paths.get("canonical_out", "diseases/03_build_canonical/out")),
        "diseases/03_build_canonical/out",
    )
    validate_out = _resolve_path(
        ETL_ROOT,
        str(paths.get("validate_out", "diseases/04_validate/out")),
        "diseases/04_validate/out",
    )
    return canonical_out, validate_out


def _load_csv_if_exists(path: Path) -> pd.DataFrame:
    """Load a CSV if it exists, otherwise return an empty dataframe."""
    if not path.exists():
        return pd.DataFrame()
    return read_csv(path)


def _issue(
    *,
    table_name: str,
    row_number: int | None,
    issue_type: str,
    severity: str,
    field_name: str = "",
    value: str = "",
    message: str = "",
) -> dict[str, Any]:
    """Build one normalized issue row."""
    return {
        "table_name": table_name,
        "row_number": "" if row_number is None else int(row_number),
        "issue_type": issue_type,
        "severity": severity,
        "field_name": field_name,
        "value": value,
        "message": message,
    }


def _required_provenance_fields(settings: dict[str, Any]) -> list[str]:
    """Return required provenance fields, using config if present."""
    validation_cfg = settings.get("validation", {})
    configured = list(validation_cfg.get("required_provenance_fields", []))
    if configured:
        return configured
    return ["source_id", "source_name", "source_url", "source_batch_id", "retrieved_at"]


def _allowed_null_fields(settings: dict[str, Any]) -> set[str]:
    """Return fields allowed to be null by config."""
    validation_cfg = settings.get("validation", {})
    return set(validation_cfg.get("allow_null_fields", []))


def _is_blank(value: object) -> bool:
    """Return True when a value is blank or missing."""
    return safe_str(value) == ""


def _is_valid_disease_key(value: object) -> bool:
    """Validate the internal disease_key format."""
    text = safe_str(value)
    return bool(text and DISEASE_KEY_RE.fullmatch(text))


def _is_valid_uuid(value: object) -> bool:
    """Validate a UUID string."""
    text = safe_str(value)
    return bool(text and UUID_RE.fullmatch(text))


def _is_valid_ontology_id(value: object) -> bool:
    """Validate ontology identifier format conservatively."""
    text = safe_str(value)
    return bool(text and ONTOLOGY_ID_RE.fullmatch(text))


def _canonical_lookup(df: pd.DataFrame) -> dict[str, str]:
    """Build a disease_id -> disease_key lookup from canonical rows."""
    if df.empty or "disease_id" not in df.columns or "disease_key" not in df.columns:
        return {}
    lookup: dict[str, str] = {}
    for _, row in df.iterrows():
        disease_id = safe_str(row.get("disease_id", ""))
        disease_key = safe_str(row.get("disease_key", ""))
        if disease_id and disease_key:
            lookup[disease_id] = disease_key
    return lookup


def _validate_required_columns(
    df: pd.DataFrame,
    required: tuple[str, ...],
    *,
    table_name: str,
    issues: list[dict[str, Any]],
) -> None:
    """Record critical issues for missing required columns."""
    validate_required_columns(df, required, table_name=table_name)


def _near_duplicate_pairs(
    values: list[str], threshold: float = 0.92
) -> list[tuple[str, str, float]]:
    """Find suspicious near-duplicate pairs among normalized strings."""
    distinct = sorted({v for v in values if v})
    pairs: list[tuple[str, str, float]] = []

    for i, left in enumerate(distinct):
        for right in distinct[i + 1 :]:
            if left == right:
                continue
            ratio = difflib.SequenceMatcher(None, left, right).ratio()
            if ratio >= threshold:
                pairs.append((left, right, ratio))
    return pairs


def _near_duplicate_threshold(settings: dict[str, Any]) -> float:
    """Read the near-duplicate detection threshold from settings."""
    return float(
        settings.get("validation", {}).get("near_duplicate_threshold", 0.92)
    )


def _validate_canonical(
    df: pd.DataFrame,
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate canonical disease rows."""
    issues: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "canonical_row_count": int(len(df)),
        "canonical_unique_disease_keys": 0,
        "canonical_unique_disease_ids": 0,
        "canonical_unmapped_count": 0,
    }

    _validate_required_columns(
        df,
        CANONICAL_REQUIRED_COLUMNS,
        table_name="diseases.csv",
        issues=issues,
    )

    if df.empty:
        issues.append(
            _issue(
                table_name="diseases.csv",
                row_number=None,
                issue_type="empty_table",
                severity="critical",
                message="Canonical disease table is empty.",
            )
        )
        return issues, summary

    disease_keys = df.get("disease_key", pd.Series(dtype=str)).map(safe_str)
    disease_ids = df.get("disease_id", pd.Series(dtype=str)).map(safe_str)
    disease_names = df.get("disease_name", pd.Series(dtype=str)).map(safe_str)

    summary["canonical_unique_disease_keys"] = int(
        disease_keys[disease_keys != ""].nunique()
    )
    summary["canonical_unique_disease_ids"] = int(
        disease_ids[disease_ids != ""].nunique()
    )

    # disease_key presence and format
    for idx, key in disease_keys.items():
        row_number = int(idx) + 2
        if _is_blank(key):
            issues.append(
                _issue(
                    table_name="diseases.csv",
                    row_number=row_number,
                    issue_type="missing_disease_key",
                    severity="critical",
                    field_name="disease_key",
                    value="",
                    message="Canonical row is missing disease_key.",
                )
            )
            continue
        if not _is_valid_disease_key(key):
            issues.append(
                _issue(
                    table_name="diseases.csv",
                    row_number=row_number,
                    issue_type="malformed_disease_key",
                    severity="critical",
                    field_name="disease_key",
                    value=key,
                    message="disease_key is not a valid slug-like key.",
                )
            )

    # disease_id presence and format
    for idx, disease_id in disease_ids.items():
        row_number = int(idx) + 2
        if _is_blank(disease_id):
            issues.append(
                _issue(
                    table_name="diseases.csv",
                    row_number=row_number,
                    issue_type="missing_disease_id",
                    severity="critical",
                    field_name="disease_id",
                    value="",
                    message="Canonical row is missing disease_id.",
                )
            )
            continue
        if not _is_valid_uuid(disease_id):
            issues.append(
                _issue(
                    table_name="diseases.csv",
                    row_number=row_number,
                    issue_type="malformed_disease_id",
                    severity="critical",
                    field_name="disease_id",
                    value=disease_id,
                    message="disease_id is not a valid UUID.",
                )
            )

    # Unique disease_key and disease_id checks
    key_counts = Counter(k for k in disease_keys if k)
    id_counts = Counter(i for i in disease_ids if i)

    for key, count in key_counts.items():
        if count > 1:
            for idx in df.index[disease_keys == key]:
                issues.append(
                    _issue(
                        table_name="diseases.csv",
                        row_number=int(idx) + 2,
                        issue_type="duplicate_disease_key",
                        severity="critical",
                        field_name="disease_key",
                        value=key,
                        message=f"disease_key appears {count} times.",
                    )
                )

    for disease_id, count in id_counts.items():
        if count > 1:
            for idx in df.index[disease_ids == disease_id]:
                issues.append(
                    _issue(
                        table_name="diseases.csv",
                        row_number=int(idx) + 2,
                        issue_type="duplicate_disease_id",
                        severity="critical",
                        field_name="disease_id",
                        value=disease_id,
                        message=f"disease_id appears {count} times.",
                    )
                )

    # Ontology checks
    unmapped_mask = df.get("ontology_id", pd.Series(dtype=str)).map(safe_str) == ""
    summary["canonical_unmapped_count"] = int(unmapped_mask.sum())
    for idx in df.index[unmapped_mask]:
        issues.append(
            _issue(
                table_name="diseases.csv",
                row_number=int(idx) + 2,
                issue_type="unmapped_disease",
                severity="warning",
                field_name="ontology_id",
                value="",
                message="Disease row has no ontology_id.",
            )
        )

    if "ontology_id" in df.columns:
        for idx, value in df["ontology_id"].items():
            ontology_id = safe_str(value)
            if ontology_id and not _is_valid_ontology_id(ontology_id):
                issues.append(
                    _issue(
                        table_name="diseases.csv",
                        row_number=int(idx) + 2,
                        issue_type="malformed_ontology_id",
                        severity="critical",
                        field_name="ontology_id",
                        value=ontology_id,
                        message="ontology_id does not match the expected identifier format.",
                    )
                )

    # Provenance completeness
    allow_null = _allowed_null_fields(settings)
    required_provenance = _required_provenance_fields(settings)
    for field in required_provenance:
        if field not in df.columns:
            if field not in allow_null:
                issues.append(
                    _issue(
                        table_name="diseases.csv",
                        row_number=None,
                        issue_type="missing_provenance_column",
                        severity="critical",
                        field_name=field,
                        value="",
                        message=f"Required provenance column '{field}' is missing.",
                    )
                )
            continue

        if field in allow_null:
            continue

        for idx, value in df[field].items():
            if _is_blank(value):
                issues.append(
                    _issue(
                        table_name="diseases.csv",
                        row_number=int(idx) + 2,
                        issue_type="missing_provenance_value",
                        severity="warning",
                        field_name=field,
                        value="",
                        message=f"Provenance field '{field}' is blank.",
                    )
                )

    # Duplicate and near-duplicate disease names
    normalized_names = disease_names.map(normalize_text)
    duplicate_names = Counter(v for v in normalized_names if v)
    for name, count in duplicate_names.items():
        if count > 1:
            for idx in df.index[normalized_names == name]:
                issues.append(
                    _issue(
                        table_name="diseases.csv",
                        row_number=int(idx) + 2,
                        issue_type="duplicate_disease_name",
                        severity="warning",
                        field_name="disease_name",
                        value=name,
                        message=f"Disease name appears {count} times after normalization.",
                    )
                )

    for left, right, ratio in _near_duplicate_pairs(
        list(normalized_names), _near_duplicate_threshold(settings)
    ):
        issues.append(
            _issue(
                table_name="diseases.csv",
                row_number=None,
                issue_type="near_duplicate_disease_name",
                severity="notice",
                field_name="disease_name",
                value=f"{left} | {right}",
                message=f"Potential near-duplicate disease names detected (similarity {ratio:.2f}).",
            )
        )

    return issues, summary


def _validate_alias_table(
    df: pd.DataFrame,
    disease_lookup_by_id: dict[str, str],
    *,
    table_name: str,
    settings: dict[str, Any],
    alias_kind: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate alias-style tables."""
    issues: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        f"{alias_kind}_row_count": int(len(df)),
        f"{alias_kind}_orphan_count": 0,
        f"{alias_kind}_empty_alias_key_count": 0,
    }

    required_columns = (
        ALIAS_REQUIRED_COLUMNS if alias_kind == "alias" else ALIAS_MAP_REQUIRED_COLUMNS
    )
    _validate_required_columns(
        df, required_columns, table_name=table_name, issues=issues
    )

    if df.empty:
        return issues, summary

    disease_key_lookup = set(disease_lookup_by_id.values())

    alias_keys = df.get("alias_key", pd.Series(dtype=str)).map(safe_str)
    disease_ids = df.get("disease_id", pd.Series(dtype=str)).map(safe_str)
    disease_keys = df.get("disease_key", pd.Series(dtype=str)).map(safe_str)

    # alias_key presence and format
    for idx, alias_key in alias_keys.items():
        row_number = int(idx) + 2
        if _is_blank(alias_key):
            summary[f"{alias_kind}_empty_alias_key_count"] += 1
            issues.append(
                _issue(
                    table_name=table_name,
                    row_number=row_number,
                    issue_type="missing_alias_key",
                    severity="critical",
                    field_name="alias_key",
                    value="",
                    message="Alias row is missing alias_key.",
                )
            )
            continue
        if not _is_valid_disease_key(alias_key):
            issues.append(
                _issue(
                    table_name=table_name,
                    row_number=row_number,
                    issue_type="malformed_alias_key",
                    severity="critical",
                    field_name="alias_key",
                    value=alias_key,
                    message="alias_key is not a valid slug-like key.",
                )
            )

    # disease_id presence and relationship integrity
    for idx, (disease_id, disease_key) in enumerate(
        zip(disease_ids, disease_keys, strict=False)
    ):
        row_number = int(df.index[idx]) + 2 if idx < len(df.index) else None
        if _is_blank(disease_id) and _is_blank(disease_key):
            summary[f"{alias_kind}_orphan_count"] += 1
            issues.append(
                _issue(
                    table_name=table_name,
                    row_number=row_number,
                    issue_type="orphan_alias",
                    severity="critical",
                    field_name="disease_id",
                    value="",
                    message="Alias row has neither disease_id nor disease_key.",
                )
            )
            continue

        if not _is_blank(disease_id):
            if not _is_valid_uuid(disease_id):
                issues.append(
                    _issue(
                        table_name=table_name,
                        row_number=row_number,
                        issue_type="malformed_disease_id",
                        severity="critical",
                        field_name="disease_id",
                        value=disease_id,
                        message="disease_id is not a valid UUID.",
                    )
                )
            elif disease_id not in disease_lookup_by_id:
                summary[f"{alias_kind}_orphan_count"] += 1
                issues.append(
                    _issue(
                        table_name=table_name,
                        row_number=row_number,
                        issue_type="orphan_alias",
                        severity="critical",
                        field_name="disease_id",
                        value=disease_id,
                        message="Alias row references a disease_id not present in diseases.csv.",
                    )
                )
            elif not _is_blank(disease_key):
                expected_key = disease_lookup_by_id[disease_id]
                if disease_key != expected_key:
                    issues.append(
                        _issue(
                            table_name=table_name,
                            row_number=row_number,
                            issue_type="inconsistent_alias_reference",
                            severity="critical",
                            field_name="disease_key",
                            value=disease_key,
                            message=f"Alias disease_key does not match the disease_key for disease_id '{disease_id}'.",
                        )
                    )
        else:
            if _is_blank(disease_key) or disease_key not in disease_key_lookup:
                summary[f"{alias_kind}_orphan_count"] += 1
                issues.append(
                    _issue(
                        table_name=table_name,
                        row_number=row_number,
                        issue_type="orphan_alias",
                        severity="critical",
                        field_name="disease_key",
                        value=disease_key,
                        message="Alias row references a disease_key not present in diseases.csv.",
                    )
                )

    # alias_type / type sanity
    type_col = (
        "alias_type"
        if "alias_type" in df.columns
        else ("type" if "type" in df.columns else None)
    )
    if type_col:
        for idx, value in df[type_col].items():
            if _is_blank(value):
                issues.append(
                    _issue(
                        table_name=table_name,
                        row_number=int(idx) + 2,
                        issue_type="missing_alias_type",
                        severity="warning",
                        field_name=type_col,
                        value="",
                        message="Alias row has a blank alias type.",
                    )
                )

    # provenance completeness
    allow_null = _allowed_null_fields(settings)
    required_provenance = _required_provenance_fields(settings)
    for field in required_provenance:
        if field not in df.columns:
            if field not in allow_null:
                issues.append(
                    _issue(
                        table_name=table_name,
                        row_number=None,
                        issue_type="missing_provenance_column",
                        severity="critical",
                        field_name=field,
                        value="",
                        message=f"Required provenance column '{field}' is missing.",
                    )
                )
            continue

        if field in allow_null:
            continue

        for idx, value in df[field].items():
            if _is_blank(value):
                issues.append(
                    _issue(
                        table_name=table_name,
                        row_number=int(idx) + 2,
                        issue_type="missing_provenance_value",
                        severity="warning",
                        field_name=field,
                        value="",
                        message=f"Provenance field '{field}' is blank.",
                    )
                )

    return issues, summary


def _validate_alias_map(
    df: pd.DataFrame,
    disease_lookup_by_id: dict[str, str],
    *,
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate flattened alias map rows."""
    issues: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "alias_map_row_count": int(len(df)),
        "alias_map_orphan_count": 0,
    }

    _validate_required_columns(
        df,
        ALIAS_MAP_REQUIRED_COLUMNS,
        table_name="disease_alias_map.csv",
        issues=issues,
    )

    if df.empty:
        return issues, summary

    for idx, alias_key in (
        df.get("alias_key", pd.Series(dtype=str)).map(safe_str).items()
    ):
        if _is_blank(alias_key):
            issues.append(
                _issue(
                    table_name="disease_alias_map.csv",
                    row_number=int(idx) + 2,
                    issue_type="missing_alias_key",
                    severity="critical",
                    field_name="alias_key",
                    value="",
                    message="Alias map row has a blank alias_key.",
                )
            )
        elif not _is_valid_disease_key(alias_key):
            issues.append(
                _issue(
                    table_name="disease_alias_map.csv",
                    row_number=int(idx) + 2,
                    issue_type="malformed_alias_key",
                    severity="critical",
                    field_name="alias_key",
                    value=alias_key,
                    message="Alias map alias_key is not a valid slug-like key.",
                )
            )

    for idx, disease_id in (
        df.get("disease_id", pd.Series(dtype=str)).map(safe_str).items()
    ):
        row_number = int(idx) + 2
        disease_key = (
            safe_str(df.at[idx, "disease_key"]) if "disease_key" in df.columns else ""
        )

        if _is_blank(disease_id) and _is_blank(disease_key):
            summary["alias_map_orphan_count"] += 1
            issues.append(
                _issue(
                    table_name="disease_alias_map.csv",
                    row_number=row_number,
                    issue_type="orphan_alias_map",
                    severity="critical",
                    field_name="disease_id",
                    value="",
                    message="Alias map row has neither disease_id nor disease_key.",
                )
            )
            continue

        if not _is_blank(disease_id):
            if not _is_valid_uuid(disease_id):
                issues.append(
                    _issue(
                        table_name="disease_alias_map.csv",
                        row_number=row_number,
                        issue_type="malformed_disease_id",
                        severity="critical",
                        field_name="disease_id",
                        value=disease_id,
                        message="Alias map disease_id is not a valid UUID.",
                    )
                )
            elif disease_id not in disease_lookup_by_id:
                summary["alias_map_orphan_count"] += 1
                issues.append(
                    _issue(
                        table_name="disease_alias_map.csv",
                        row_number=row_number,
                        issue_type="orphan_alias_map",
                        severity="critical",
                        field_name="disease_id",
                        value=disease_id,
                        message="Alias map row references a disease_id not present in diseases.csv.",
                    )
                )
            elif not _is_blank(disease_key):
                expected_key = disease_lookup_by_id[disease_id]
                if disease_key != expected_key:
                    issues.append(
                        _issue(
                            table_name="disease_alias_map.csv",
                            row_number=row_number,
                            issue_type="inconsistent_alias_reference",
                            severity="critical",
                            field_name="disease_key",
                            value=disease_key,
                            message="Alias map disease_key does not match the disease_key for disease_id.",
                        )
                    )
        else:
            if disease_key not in set(disease_lookup_by_id.values()):
                summary["alias_map_orphan_count"] += 1
                issues.append(
                    _issue(
                        table_name="disease_alias_map.csv",
                        row_number=row_number,
                        issue_type="orphan_alias_map",
                        severity="critical",
                        field_name="disease_key",
                        value=disease_key,
                        message="Alias map row references a disease_key not present in diseases.csv.",
                    )
                )

    # Deduplicate alias map rows should be unique enough for search.
    if "alias_key" in df.columns and "disease_key" in df.columns:
        alias_pairs = list(
            zip(
                df["alias_key"].map(safe_str).tolist(),
                df["disease_key"].map(safe_str).tolist(),
                strict=False,
            )
        )
        pair_counts = Counter((a, d) for a, d in alias_pairs if a and d)
        for (alias_key, disease_key), count in pair_counts.items():
            if count > 1:
                for idx in df.index[
                    (df["alias_key"].map(safe_str) == alias_key)
                    & (df["disease_key"].map(safe_str) == disease_key)
                ]:
                    issues.append(
                        _issue(
                            table_name="disease_alias_map.csv",
                            row_number=int(idx) + 2,
                            issue_type="duplicate_alias_map_pair",
                            severity="warning",
                            field_name="alias_key",
                            value=alias_key,
                            message=f"Alias map pair appears {count} times.",
                        )
                    )

    return issues, summary


def run(settings_path: str | Path = DEFAULT_SETTINGS_PATH) -> dict[str, Any]:
    """Run the validation step and return a summary dictionary."""
    settings_path = Path(settings_path)
    settings = load_settings("diseases")
    logger = shared_setup_logging("diseases.04_validate", settings)

    canonical_out, validate_out = _resolve_paths(settings, settings_path)
    ensure_dir(validate_out)

    diseases_path = canonical_out / CANONICAL_FILE
    aliases_path = canonical_out / ALIASES_FILE
    alias_map_path = canonical_out / ALIAS_MAP_FILE

    diseases_df = _load_csv_if_exists(diseases_path)
    aliases_df = _load_csv_if_exists(aliases_path)
    alias_map_df = _load_csv_if_exists(alias_map_path)

    disease_lookup_by_id = _canonical_lookup(diseases_df)
    disease_lookup_by_key = set(disease_lookup_by_id.values())

    all_issues: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "module_name": settings.get("module_name", "disease_etl"),
        "step": "04_validate",
        "batch_id": safe_str(settings.get("batch_id", "")),
        "input_dir": str(canonical_out),
        "validate_out": str(validate_out),
        "canonical_file": str(diseases_path),
        "aliases_file": str(aliases_path),
        "alias_map_file": str(alias_map_path),
        "timestamp": now_iso(),
    }

    if diseases_df.empty:
        all_issues.append(
            _issue(
                table_name="diseases.csv",
                row_number=None,
                issue_type="missing_input",
                severity="critical",
                message=f"Missing or empty canonical disease file: {diseases_path}",
            )
        )

    if aliases_df.empty:
        all_issues.append(
            _issue(
                table_name="disease_aliases.csv",
                row_number=None,
                issue_type="missing_input",
                severity="critical",
                message=f"Missing or empty alias file: {aliases_path}",
            )
        )

    canonical_issues, canonical_summary = _validate_canonical(diseases_df, settings)
    alias_issues, alias_summary = _validate_alias_table(
        aliases_df,
        disease_lookup_by_id,
        table_name="disease_aliases.csv",
        settings=settings,
        alias_kind="alias",
    )
    alias_map_issues, alias_map_summary = _validate_alias_map(
        alias_map_df,
        disease_lookup_by_id,
        settings=settings,
    )

    all_issues.extend(canonical_issues)
    all_issues.extend(alias_issues)
    all_issues.extend(alias_map_issues)

    severity_counts = Counter(issue["severity"] for issue in all_issues)
    issue_type_counts = Counter(issue["issue_type"] for issue in all_issues)

    summary.update(canonical_summary)
    summary.update(alias_summary)
    summary.update(alias_map_summary)
    summary["issue_count"] = int(len(all_issues))
    summary["critical_issue_count"] = int(severity_counts.get("critical", 0))
    summary["warning_issue_count"] = int(severity_counts.get("warning", 0))
    summary["notice_issue_count"] = int(severity_counts.get("notice", 0))
    summary["severity_counts"] = dict(severity_counts)
    summary["issue_type_counts"] = dict(issue_type_counts)
    summary["passed"] = summary["critical_issue_count"] == 0

    issues_df = pd.DataFrame(
        all_issues,
        columns=[
            "table_name",
            "row_number",
            "issue_type",
            "severity",
            "field_name",
            "value",
            "message",
        ],
    )

    report_csv = validate_out / "validation_report.csv"
    issues_csv = validate_out / "issues.csv"
    report_json = validate_out / "validation_report.json"

    write_csv(issues_df, report_csv)
    write_csv(issues_df, issues_csv)

    with report_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        f.write("\n")

    log_path = validate_out / "run.log"
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"Validation completed at {summary['timestamp']}\n")
        f.write(f"Passed: {summary['passed']}\n")
        f.write(f"Critical issues: {summary['critical_issue_count']}\n")
        f.write(f"Warnings: {summary['warning_issue_count']}\n")
        f.write(f"Notices: {summary['notice_issue_count']}\n")
        f.write(f"Canonical input: {diseases_path}\n")
        f.write(f"Alias input: {aliases_path}\n")
        f.write(f"Alias map input: {alias_map_path}\n")

    logger.info(
        "Validation complete: passed=%s, critical=%s, warnings=%s, notices=%s",
        summary["passed"],
        summary["critical_issue_count"],
        summary["warning_issue_count"],
        summary["notice_issue_count"],
    )

    stop_on_validation_error = bool(
        settings.get("validation", {}).get("stop_on_validation_error", True)
    )
    if stop_on_validation_error and not summary["passed"]:
        raise ValueError(
            f"Validation failed with {summary['critical_issue_count']} critical issue(s). "
            f"See {report_csv} and {report_json}."
        )

    return summary


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate canonical disease outputs before export."
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
