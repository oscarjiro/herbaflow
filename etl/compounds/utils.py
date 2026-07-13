"""Compound-specific ETL utilities."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.identity import (  # noqa: F401 — re-exported for downstream scripts
    COMPOUND_ALIAS_NS,
    COMPOUND_NS,
    compound_alias_id,
    compound_canonical_key,
    compound_id,
    compound_id_from_key,
    normalize_cas,
)
