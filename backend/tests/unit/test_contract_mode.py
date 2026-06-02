"""Agreement test: analysis_runs.mode is one set across contract, Pydantic, and DB CHECK."""
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts import ANALYSIS_MODES
from app.schemas.analysis import CreateAnalysisRequest

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase" / "migrations" / "20260602000003_type_validation.sql"
)


def test_contract_anchor():
    assert set(ANALYSIS_MODES) == {"auto", "guided"}


def test_db_check_matches_contract():
    sql = MIGRATION.read_text(encoding="utf-8")
    m = re.search(r"mode\s+in\s*\(([^)]*)\)", sql, re.IGNORECASE)
    assert m, "no `mode in (...)` CHECK found in the migration"
    db_modes = {part.strip().strip("'\"") for part in m.group(1).split(",")}
    assert db_modes == set(ANALYSIS_MODES)


def test_pydantic_accepts_contract_modes():
    for mode in ANALYSIS_MODES:
        req = CreateAnalysisRequest(name="x", mode=mode, disease_id="d1")
        assert req.mode == mode


def test_pydantic_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        CreateAnalysisRequest(name="x", mode="semi", disease_id="d1")
