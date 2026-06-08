"""The single source of timezone-aware UTC timestamps."""

from __future__ import annotations

from datetime import UTC, datetime


def now_utc() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)
