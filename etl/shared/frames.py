# etl/shared/frames.py
"""Pandas DataFrame I/O helpers for the ETL pipeline.

The two pandas-native modules (diseases, disease_targets) share these. Kept
separate from shared/utils.py (which is stdlib list[dict] I/O) so that the two
container idioms never collide under one name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

from shared.utils import ensure_dir


def read_frame(path: str | Path, **kwargs) -> pd.DataFrame:
    """Read a CSV into a DataFrame, preserving strings (no NaN coercion)."""
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        na_values=[],
        **kwargs,
    )


def write_frame(df: pd.DataFrame, path: str | Path, index: bool = False) -> Path:
    """Write a DataFrame to CSV, creating the parent directory if needed."""
    out_path = Path(path)
    ensure_dir(out_path.parent)
    df.to_csv(out_path, index=index)
    return out_path


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
