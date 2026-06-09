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


def test_adme_defaults_agree_with_contract_properties() -> None:
    """adme_defaults() must equal the ``default`` field of every adme property in the contract."""
    props = contracts.pipeline_parameters()["adme"]["properties"]
    expected = {name: spec["default"] for name, spec in props.items()}
    assert contracts.adme_defaults() == expected


def test_create_schema_cap_matches_contract() -> None:
    from app.schemas.analysis import AnalysisCreate

    field = AnalysisCreate.model_fields["plant_ids"]
    maxes = [m for m in field.metadata if getattr(m, "max_length", None) is not None]
    assert maxes and maxes[0].max_length == contracts.max_plants()


def test_target_defaults_match_contract():
    d = contracts.target_defaults()
    assert d == {"min_pchembl": 5.0, "min_assay_confidence": 7}
    assert "human_only" not in d
    meta = contracts.target_param_meta()
    assert meta["min_pchembl"]["recommended_max"] == 7.0
    assert meta["min_assay_confidence"]["max"] == 9
