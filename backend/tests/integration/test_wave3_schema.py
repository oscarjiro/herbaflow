"""Wave 3: assert the migrated DB shape (runs against the testcontainer built from all migrations)."""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_dropped_columns_and_tables_gone(session):
    async def cols(tbl):
        rows = await session.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_schema='public' and table_name=:t"
            ),
            {"t": tbl},
        )
        return {r[0] for r in rows}

    assert "canonical_key" not in await cols("plants")
    assert "canonical_key" not in await cols("compounds")
    assert "canonical_key" not in await cols("targets")
    assert "canonical_key" not in await cols("diseases")
    assert "qed_score" not in await cols("compounds")
    assert "idempotency_key" not in await cols("analysis_runs")
    for t in (
        "plants",
        "compounds",
        "targets",
        "diseases",
        "plant_compounds",
        "compound_targets",
        "disease_targets",
    ):
        assert "source_id" not in await cols(t), t

    tables = await session.execute(
        text("select table_name from information_schema.tables where table_schema='public'")
    )
    names = {r[0] for r in tables}
    for gone in (
        "plant_aliases",
        "compound_aliases",
        "target_aliases",
        "disease_aliases",
        "source_systems",
    ):
        assert gone not in names, gone
    assert "gbif_key" in await cols("plants")


@pytest.mark.asyncio
async def test_natural_key_constraints(session):
    async def constraints(tbl):
        rows = await session.execute(
            text(
                "select constraint_type, constraint_name from information_schema.table_constraints "
                "where table_schema='public' and table_name=:t"
            ),
            {"t": tbl},
        )
        return {(r[0], r[1]) for r in rows}

    assert ("UNIQUE", "plants_gbif_key_key") in await constraints("plants")
    assert ("UNIQUE", "compounds_inchi_key_key") in await constraints("compounds")
    assert ("UNIQUE", "targets_uniprot_accession_key") in await constraints("targets")
    assert ("UNIQUE", "diseases_ontology_id_key") in await constraints("diseases")

    async def notnull(tbl, col):
        row = await session.execute(
            text(
                "select is_nullable from information_schema.columns "
                "where table_schema='public' and table_name=:t and column_name=:c"
            ),
            {"t": tbl, "c": col},
        )
        return row.scalar_one() == "NO"

    assert await notnull("plants", "gbif_key")
    assert await notnull("diseases", "ontology_id")
    assert await notnull("compound_targets", "prediction_method")
    assert await notnull("analysis_runs", "status")
    assert await notnull("analysis_runs", "created_at")
    # inchi_key / uniprot_accession stay NULLABLE (some classes have no such id) — UNIQUE only
    assert not await notnull("compounds", "inchi_key")
    assert not await notnull("targets", "uniprot_accession")
