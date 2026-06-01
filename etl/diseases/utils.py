"""Shared support utilities for the disease ETL pipeline.

This module centralizes the small set of reusable helpers used across the
seed, normalization, ontology mapping, canonical build, validation, and
export steps. It is intentionally compact and practical: filesystem helpers,
CSV I/O, text and key normalization, logging setup, timestamp helpers,
required-column validation, and simple deduplication.

The goal is to keep step scripts thin, readable, and idempotent without
introducing a large general-purpose utility layer.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging, ensure_dir, now_iso
from shared.identity import (
    DISEASE_NS,
    DISEASE_ALIAS_NS,
    disease_canonical_key,
    disease_id,
    disease_alias_id,
    slugify,
    ALIAS_PRIORITY,
    pick_alias,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DISEASES_DIR = PROJECT_ROOT / "diseases"
SETTINGS_PATH = DISEASES_DIR / "settings.yml"


_MISSING_STRINGS = {
    "",
    "na",
    "n/a",
    "none",
    "null",
    "nan",
    "-",
    "unknown",
    "unspecified",
}


def read_csv(path: str | Path, **kwargs) -> pd.DataFrame:
    """Read a CSV file using sensible defaults for ETL work.

    Default behavior preserves strings where possible and keeps blank values
    from being over-interpreted by pandas.
    """
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        na_values=[],
        **kwargs,
    )


def write_csv(df: pd.DataFrame, path: str | Path, index: bool = False) -> Path:
    """Write a dataframe to CSV, creating the parent directory if needed."""
    out_path = Path(path)
    ensure_dir(out_path.parent)
    df.to_csv(out_path, index=index)
    return out_path


def normalize_text(value: object) -> str:
    """Normalize text for comparison and key generation.

    The function trims whitespace, converts internal whitespace to single
    spaces, and lowercases the value. Missing-like strings are converted to
    an empty string.
    """
    text = safe_str(value)
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip().lower()
    return "" if text in _MISSING_STRINGS else text


def make_slug_key(value: object) -> str:
    """Build a stable canonical key from free text.

    The key is lowercase ASCII-ish text with non-alphanumeric characters
    collapsed to single underscores. This is intended for canonical disease
    keys, alias keys, and join-friendly identifiers within the pipeline.
    """
    text = normalize_text(value)
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def canonical_key(value: object) -> str:
    """Alias for the pipeline's canonical key builder."""
    return make_slug_key(value)


def safe_str(value: object) -> str:
    """Convert a value to a clean string and normalize missing values to ''."""
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
    """Raise a ValueError if any required columns are missing."""
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"{table_name} is missing required columns: {', '.join(missing)}"
        )


