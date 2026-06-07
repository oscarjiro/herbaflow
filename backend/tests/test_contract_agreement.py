"""The migration baseline's analysis_runs.mode CHECK must match the contract mode enum."""

import re
from pathlib import Path

from app import contracts

_BASELINE = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260608000005_baseline_operational.sql"
)


def _mode_check_values() -> set[str]:
    sql = _BASELINE.read_text(encoding="utf-8")
    # Match: mode ... check (mode in ('auto', 'guided'))  (case-insensitive, flexible whitespace)
    m = re.search(r"mode\s+in\s*\(([^)]*)\)", sql, flags=re.IGNORECASE)
    assert m, "mode CHECK not found in the operational baseline migration"
    return {v.strip().strip("'\"") for v in m.group(1).split(",")}


def test_mode_check_matches_contract():
    assert _mode_check_values() == set(contracts.modes())
