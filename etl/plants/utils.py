"""Plant-specific ETL utilities."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.identity import (  # noqa: F401 — re-exported for downstream scripts
    PLANT_ALIAS_NS,
    PLANT_NS,
    plant_alias_id,
    plant_canonical_key,
    plant_id,
)
from shared.utils import normalize_unicode, normalize_whitespace


def split_scientific_name(name: str) -> tuple[str, str]:
    """Split 'Genus species Author' into ('Genus species', 'Author').

    Authorship is detected as any tokens after the second that begin with
    an uppercase letter or an open parenthesis.
    """
    tokens = name.strip().split()
    if len(tokens) <= 2:
        return name.strip(), ""
    if tokens[2][0].isupper() or tokens[2].startswith("("):
        return " ".join(tokens[:2]), " ".join(tokens[2:])
    return name.strip(), ""


def build_canonical_lookup_key(name: str) -> str:
    """Return a normalized, lowercased key suitable for GBIF lookup matching."""
    return normalize_whitespace(normalize_unicode(name)).lower()
