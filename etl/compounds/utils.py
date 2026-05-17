"""Compound-specific ETL utilities."""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.utils import stable_id, safe_str

COMPOUND_NS: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.compounds")
COMPOUND_ALIAS_NS: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.compound_aliases")


def normalize_cas(cas: str) -> tuple[str, bool, str]:
    """Validate and normalize a CAS registry number.

    Returns (normalized_cas, is_valid, reason).
    The checksum digit is the remainder of the sum of (digit * position) divided by 10,
    where positions count from 1 on the right.
    """
    cas = safe_str(cas)
    if not cas:
        return "", False, "empty"

    # Strip spaces; accept formats like 50-00-0 or 50000
    cleaned = re.sub(r"\s+", "", cas)
    # Normalize to hyphenated form
    digits_only = re.sub(r"-", "", cleaned)
    if not digits_only.isdigit():
        return cas, False, "non-numeric characters"
    if len(digits_only) < 3:
        return cas, False, "too short"

    check_digit = int(digits_only[-1])
    body = digits_only[:-1]
    total = sum(int(d) * (i + 1) for i, d in enumerate(reversed(body)))
    expected = total % 10

    if check_digit != expected:
        return cleaned, False, f"checksum mismatch: expected {expected}, got {check_digit}"

    # Rebuild hyphenated form: last group = 1 digit, second = 2 digits, first = rest
    last = digits_only[-1]
    second = digits_only[-3:-1]
    first = digits_only[:-3]
    normalized = f"{first}-{second}-{last}"
    return normalized, True, "ok"


def compound_id(key: str) -> str:
    """Return a deterministic UUID v5 for the given compound identity key (e.g. InChIKey)."""
    return stable_id(COMPOUND_NS, str(key))


def compound_alias_id(compound_uuid: str, alias_name: str) -> str:
    """Return a deterministic UUID v5 for a compound alias."""
    return stable_id(COMPOUND_ALIAS_NS, f"{compound_uuid}:{alias_name}")
