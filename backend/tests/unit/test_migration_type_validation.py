"""Structural guard on the type-tightening migration (authored, not applied here)."""
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase" / "migrations" / "20260602000003_type_validation.sql"
)


def _norm() -> str:
    # Collapse all whitespace so spacing/alignment in the SQL doesn't break matches.
    return " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())


def test_migration_file_exists():
    assert MIGRATION.is_file()


def test_every_entity_id_column_becomes_uuid():
    sql = _norm()
    for frag in [
        "alter column plant_id type uuid",
        "alter column compound_id type uuid",
        "alter column target_id type uuid",
        "alter column disease_id type uuid",
        "alter column plant_compound_id type uuid",
        "alter column compound_target_id type uuid",
        "alter column disease_target_id type uuid",
        "alter column alias_id type uuid",
        "alter column compound_alias_id type uuid",
        "alter column target_alias_id type uuid",
        "alter column disease_alias_id type uuid",
    ]:
        assert frag in sql, f"missing: {frag}"


def test_fks_dropped_and_readded():
    sql = _norm()
    assert "drop constraint if exists plant_compounds_plant_id_fkey" in sql
    assert "add constraint plant_compounds_plant_id_fkey" in sql
    assert "add constraint analysis_runs_disease_id_fkey" in sql


def test_control_only_checks_present():
    sql = _norm()
    assert "prediction_method in ('chembl_bioactivity','pubchem_bioassay','stp_import')" in sql
    # status is a dynamic stage-derived string (no fixed-vocab CHECK) — see migration note.
    assert "status in (" not in sql
    assert "mode in ('auto','guided')" in sql


def test_range_checks_present():
    sql = _norm()
    assert "num_ro5_violations between 0 and 4" in sql
    assert "current_stage between 1 and 8" in sql


def test_jsonb_object_checks_present():
    sql = _norm()
    assert "alter column parameters set not null" in sql
    assert "jsonb_typeof(parameters) = 'object'" in sql
    assert "jsonb_typeof(stage_results) = 'object'" in sql
