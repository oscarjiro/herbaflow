from pathlib import Path

MIG = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "20260602000001_deadweight_trim.sql"


def test_migration_exists_and_drops_expected_objects():
    sql = MIG.read_text(encoding="utf-8").lower()
    for tbl in ("target_rankings", "ppi_edges", "analysis_run_ppi_edges", "pathways",
                "target_pathways", "analysis_run_plants", "analysis_run_compounds",
                "analysis_run_targets", "analysis_run_diseases"):
        assert f"drop table if exists {tbl}" in sql, f"missing drop for {tbl}"
    assert sql.count("drop column if exists confidence") >= 7
    assert "drop column if exists evidence_type" in sql
    assert "drop column if exists source_plant_raw_id" in sql
    assert "drop column if exists source_compound_raw_id" in sql
    assert "cron.schedule" in sql
    # never re-add the already-present unique
    assert "add constraint" not in sql or "canonical_key" not in sql.split("add constraint")[1][:80]
