# backend/tests/unit/test_s3_migration.py
from pathlib import Path

MIG = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / \
    "20260602000002_deep_link_provenance.sql"


def test_migration_exists_and_changes_expected_objects():
    sql = MIG.read_text(encoding="utf-8").lower()
    # add source_url to the 3 link tables
    for tbl in ("plant_compounds", "compound_targets", "disease_targets"):
        assert f"alter table {tbl}" in sql and "add column if not exists source_url" in sql, \
            f"missing source_url add for {tbl}"
    assert sql.count("add column if not exists source_url") >= 3
    # drop import_batches
    assert "drop table if exists import_batches" in sql
    # drop source_batch_id from 8 entity/alias tables
    assert sql.count("drop column if exists source_batch_id") >= 8
    for tbl in ("plants", "plant_aliases", "compounds", "compound_aliases",
                "targets", "target_aliases", "diseases", "disease_aliases"):
        assert tbl in sql
