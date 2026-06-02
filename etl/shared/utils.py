"""Shared ETL utilities for the herbaflow pipeline."""

from __future__ import annotations

import csv
import json
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ETL_ROOT = Path(__file__).resolve().parent.parent  # etl/shared/ -> etl/


def load_settings(module_name: str) -> dict:
    """Load and deep-merge shared settings with module-specific settings."""
    shared_path = ETL_ROOT / "shared" / "settings.yml"
    module_path = ETL_ROOT / module_name / "settings.yml"

    with open(shared_path, encoding="utf-8") as f:
        shared: dict = yaml.safe_load(f) or {}

    with open(module_path, encoding="utf-8") as f:
        module: dict = yaml.safe_load(f) or {}

    return _deep_merge(shared, module)


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def setup_logging(name: str, cfg: dict) -> logging.Logger:
    """Configure and return a named logger using settings from cfg."""
    log_cfg = cfg.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    fmt = log_cfg.get("format", "%(asctime)s | %(levelname)s | %(message)s")
    logging.basicConfig(level=level, format=fmt)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger


def ensure_dir(path: Path | str) -> Path:
    """Create directory and all parents if they don't exist."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_run_id(prefix: str) -> str:
    """Return a timestamped run identifier: {prefix}_{YYYYMMDD_HHMMSS}."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}"


def read_csv(path: Path | str, **kwargs) -> list[dict]:
    """Read a CSV file and return a list of dicts. Handles UTF-8 BOM."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, **kwargs))


def write_csv(
    rows: list[dict],
    path: Path | str,
    fieldnames: list[str] | None = None,
) -> None:
    """Write rows to a CSV file, creating parent directories as needed."""
    path = Path(path)
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(data: Any, path: Path | str) -> None:
    """Write data as pretty-printed JSON, creating parent directories as needed."""
    path = Path(path)
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_whitespace(s: str | None) -> str:
    """Trim leading/trailing whitespace and collapse internal runs."""
    if not s:
        return ""
    return " ".join(str(s).split())


def normalize_unicode(s: str | None) -> str:
    """Apply NFKC Unicode normalization."""
    if not s:
        return ""
    return unicodedata.normalize("NFKC", str(s))


def to_key(s: str | None) -> str:
    """Normalize to a lowercase underscore-separated lookup key, stripping punctuation."""
    if not s:
        return ""
    s = normalize_unicode(s).lower()
    s = re.sub(r"[^\w\s]", "", s)
    return normalize_whitespace(s).replace(" ", "_")


def safe_str(v: Any) -> str:
    """Return str(v).strip(), or '' if v is None."""
    if v is None:
        return ""
    return str(v).strip()


_MISSING = {
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


def clean_str(v: Any) -> str:
    """Like safe_str, but maps known missing-markers (and NaN) to ''."""
    if v is None:
        return ""
    try:
        # pandas float NaN guard without importing pandas
        if isinstance(v, float) and v != v:
            return ""
    except Exception:
        pass
    text = str(v).strip()
    return "" if text.lower() in _MISSING else text


def normalize_text(v: Any) -> str:
    """Lowercase, collapse internal whitespace, fold missing-markers to ''."""
    text = clean_str(v)
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip().lower()
    return "" if text in _MISSING else text


def stable_id(namespace: uuid.UUID, key: str) -> str:
    """Return a deterministic UUID v5 string for the given namespace and key."""
    return str(uuid.uuid5(namespace, key))
