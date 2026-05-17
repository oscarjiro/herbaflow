"""Shared utilities for the disease_targets ETL pipeline."""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging, ensure_dir, now_iso, stable_id  # noqa: F401

TARGET_NS: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.targets")
TARGET_ALIAS_NS: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.target_aliases")
DISEASE_TARGET_NS: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.disease_targets")


def target_id(canonical_key: str) -> str:
    return stable_id(TARGET_NS, str(canonical_key))


def target_alias_id(target_uuid: str, alias_name: str) -> str:
    return stable_id(TARGET_ALIAS_NS, f"{target_uuid}:{alias_name}")


def disease_target_id(disease_uuid: str, target_uuid: str) -> str:
    return stable_id(DISEASE_TARGET_NS, f"{disease_uuid}:{target_uuid}")


def canonical_key_for_target(uniprot_accession: str | None, ensembl_id: str) -> str:
    """Build canonical_key: 'uniprot:{acc}' if available, else 'ensembl:{id}'."""
    acc = (uniprot_accession or "").strip()
    if acc:
        return f"uniprot:{acc}"
    return f"ensembl:{ensembl_id.strip()}"


_MISSING_STRINGS = {"", "na", "n/a", "none", "null", "nan", "-", "unknown", "unspecified"}


def read_csv(path: str | Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[], **kwargs)


def write_csv(df: pd.DataFrame, path: str | Path, index: bool = False) -> Path:
    out_path = Path(path)
    ensure_dir(out_path.parent)
    df.to_csv(out_path, index=index)
    return out_path


def normalize_text(value: object) -> str:
    text = safe_str(value)
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip().lower()
    return "" if text in _MISSING_STRINGS else text


def make_slug_key(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def safe_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in _MISSING_STRINGS else text


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: Sequence[str],
    *,
    table_name: str = "dataframe",
) -> None:
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"{table_name} is missing required columns: {', '.join(missing)}")


def dedupe_by_key(
    df: pd.DataFrame,
    key_column: str,
    *,
    keep: str = "first",
) -> pd.DataFrame:
    if key_column not in df.columns:
        raise ValueError(f"Cannot dedupe: missing key column '{key_column}'")
    return df.drop_duplicates(subset=[key_column], keep=keep).copy()


def clean_missing_values(
    df: pd.DataFrame, columns: Iterable[str] | None = None
) -> pd.DataFrame:
    out = df.copy()
    target_cols = list(columns) if columns is not None else list(out.columns)
    for col in target_cols:
        if col not in out.columns:
            continue
        out[col] = out[col].map(safe_str)
    return out
