"""Shared utilities for the disease_targets ETL pipeline."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging, ensure_dir, now_iso  # noqa: F401
from shared.identity import (  # noqa: F401
    TARGET_NS,
    TARGET_ALIAS_NS,
    DISEASE_TARGET_NS,
    target_canonical_key,
    target_id,
    target_id_from_key,
    target_alias_id,
    disease_target_id,
    fold_isoform,
)


def canonical_key_for_target(uniprot_accession: str | None, ensembl_id: str) -> str:
    """canonical_key: 'uniprot:{folded acc}' if available, else 'ensembl:{id}'."""
    return target_canonical_key(uniprot=uniprot_accession, ensembl=ensembl_id)


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


