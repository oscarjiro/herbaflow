"""Plant-specific ETL utilities."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.utils import normalize_whitespace, normalize_unicode, stable_id

PLANT_NS: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.plants")
PLANT_ALIAS_NS: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.plant_aliases")


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


def plant_id(gbif_usage_key: str | int) -> str:
    """Return a deterministic UUID v5 for the given GBIF usage key."""
    return stable_id(PLANT_NS, str(gbif_usage_key))


def alias_id(plant_uuid: str, alias_type: str, alias_name: str) -> str:
    """Return a deterministic UUID v5 for a plant alias."""
    return stable_id(PLANT_ALIAS_NS, f"{plant_uuid}:{alias_type}:{alias_name}")
