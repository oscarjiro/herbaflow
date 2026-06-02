"""Guard: downstream validate/export required-column lists must match trimmed build outputs.

Prior commits trimmed columns from the BUILD-stage outputs. The validate and export
stages still enumerated the dropped columns in their required/expected column lists, so
at re-derive time the hard column check would fail on absent-but-required columns.

This guard asserts each downstream list excludes the dropped columns, AND that the
KEPT tables (disease entity, disease alias map, plant_compounds link, plant/compound
entity source columns) still contain their source columns — proving no over-drop.

Approach mirrors test_alias_outputs_no_source.py / test_entity_outputs_trimmed.py:
import the constant where importable, source-scan otherwise.
"""
import importlib.util
import pathlib
import re
import sys

ETL = pathlib.Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ETL / rel)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _extract_list_literal(text: str, name: str) -> set[str]:
    m = re.search(rf"{re.escape(name)}\s*=\s*[\[\(]([^\]\)]*)[\]\)]", text, re.DOTALL)
    assert m, f"Could not find {name} in source"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


# Dropped column inventories ------------------------------------------------
PLANT_ENTITY_DROPPED = {
    "authorship",
    "taxonomic_status",
    "rank",
    "gbif_usage_key",
    "gbif_accepted_usage_key",
    "gbif_species_key",
    "gbif_genus_key",
    "gbif_family_key",
    "gbif_kingdom_key",
}
GBIF_KEYS = {
    "gbif_usage_key",
    "gbif_accepted_usage_key",
    "gbif_species_key",
    "gbif_genus_key",
    "gbif_family_key",
    "gbif_kingdom_key",
}
SOURCE_NAME_URL = {"source_name", "source_url"}


# ---------------------------------------------------------------------------
# plants/05_validate
# ---------------------------------------------------------------------------
plants_validate = _load("plants/05_validate/run.py", "p05v")


def test_plants_validate_required_plant_columns_drop_entity_columns():
    cols = set(plants_validate.REQUIRED_PLANT_COLUMNS)
    assert PLANT_ENTITY_DROPPED.isdisjoint(cols), (
        f"REQUIRED_PLANT_COLUMNS still contains: {PLANT_ENTITY_DROPPED & cols}"
    )


def test_plants_validate_required_plant_columns_keep_source_and_family():
    cols = set(plants_validate.REQUIRED_PLANT_COLUMNS)
    for kept in ("family_name", "source_name", "source_url"):
        assert kept in cols, f"REQUIRED_PLANT_COLUMNS lost kept column {kept}"


def test_plants_validate_required_alias_columns_drop_source():
    cols = set(plants_validate.REQUIRED_ALIAS_COLUMNS)
    assert SOURCE_NAME_URL.isdisjoint(cols), (
        f"REQUIRED_ALIAS_COLUMNS still contains: {SOURCE_NAME_URL & cols}"
    )


# ---------------------------------------------------------------------------
# plants/06_export
# ---------------------------------------------------------------------------
plants_export = _load("plants/06_export/run.py", "p06e")


def test_plants_export_schema_columns_drop_entity_columns():
    cols = set(plants_export.PLANTS_SCHEMA_COLUMNS)
    assert PLANT_ENTITY_DROPPED.isdisjoint(cols), (
        f"PLANTS_SCHEMA_COLUMNS still contains: {PLANT_ENTITY_DROPPED & cols}"
    )


def test_plants_export_id_like_columns_drop_gbif_keys():
    cols = set(plants_export.ID_LIKE_COLUMNS)
    assert GBIF_KEYS.isdisjoint(cols), (
        f"ID_LIKE_COLUMNS still contains: {GBIF_KEYS & cols}"
    )
    assert "plant_id" in cols and "alias_id" in cols, "ID_LIKE_COLUMNS lost kept id columns"


# ---------------------------------------------------------------------------
# diseases/04_validate  (source-scan tuples)
# ---------------------------------------------------------------------------
DISEASES_VALIDATE_TEXT = (ETL / "diseases/04_validate/run.py").read_text(encoding="utf-8")


def test_diseases_validate_alias_required_drops_source():
    cols = _extract_list_literal(DISEASES_VALIDATE_TEXT, "ALIAS_REQUIRED_COLUMNS")
    banned = {"source_id", "source_name", "source_url"}
    assert banned.isdisjoint(cols), (
        f"ALIAS_REQUIRED_COLUMNS still contains: {banned & cols}"
    )


def test_diseases_validate_canonical_required_keeps_source_id():
    # over-drop guard: the disease ENTITY keeps seed-sourced source columns
    cols = _extract_list_literal(DISEASES_VALIDATE_TEXT, "CANONICAL_REQUIRED_COLUMNS")
    assert "source_id" in cols, "CANONICAL_REQUIRED_COLUMNS must keep source_id"


def test_diseases_validate_alias_map_required_keeps_source_id():
    # over-drop guard: the disease_alias_map intentionally keeps source columns
    cols = _extract_list_literal(DISEASES_VALIDATE_TEXT, "ALIAS_MAP_REQUIRED_COLUMNS")
    assert "source_id" in cols, "ALIAS_MAP_REQUIRED_COLUMNS must keep source_id"


# ---------------------------------------------------------------------------
# compounds/06_validate  (source-scan list literals)
# ---------------------------------------------------------------------------
COMPOUNDS_VALIDATE_TEXT = (ETL / "compounds/06_validate/run.py").read_text(encoding="utf-8")


def test_compounds_validate_compounds_columns_drop_lipinski_source():
    cols = _extract_list_literal(COMPOUNDS_VALIDATE_TEXT, "COMPOUNDS_COLUMNS")
    assert "lipinski_source" not in cols, (
        "COMPOUNDS_COLUMNS still lists lipinski_source"
    )
    # over-drop guard: compound entity keeps source columns
    assert "source_name" in cols and "source_url" in cols, (
        "COMPOUNDS_COLUMNS must keep source_name/source_url"
    )


def test_compounds_validate_aliases_columns_drop_source():
    cols = _extract_list_literal(COMPOUNDS_VALIDATE_TEXT, "ALIASES_COLUMNS")
    assert SOURCE_NAME_URL.isdisjoint(cols), (
        f"ALIASES_COLUMNS still contains: {SOURCE_NAME_URL & cols}"
    )


def test_compounds_validate_plant_compounds_columns_keep_source_name():
    # over-drop guard: plant_compounds link keeps source_name/source_url
    cols = _extract_list_literal(COMPOUNDS_VALIDATE_TEXT, "PLANT_COMPOUNDS_COLUMNS")
    assert "source_name" in cols, "PLANT_COMPOUNDS_COLUMNS must keep source_name"


# ---------------------------------------------------------------------------
# plants/04_build_canonical/run_part2 — dead GBIF_ID_FIELDS constant removed
# ---------------------------------------------------------------------------
def test_plants_build_part2_has_no_dead_gbif_id_fields_constant():
    text = (ETL / "plants/04_build_canonical/run_part2.py").read_text(encoding="utf-8")
    assert not re.search(r"^GBIF_ID_FIELDS\s*=", text, re.MULTILINE), (
        "dead GBIF_ID_FIELDS constant still defined in run_part2.py"
    )


def test_plants_validate_aliases_does_not_read_dropped_source_name():
    # plant_aliases dropped source_name; validate_aliases must not check it, or every
    # alias row trips source_name_looks_like_plant_name on the now-empty column.
    text = (ETL / "plants/05_validate/run.py").read_text(encoding="utf-8")
    m = re.search(r"def validate_aliases\b(.+?)(?=\ndef )", text, re.DOTALL)
    assert m, "could not locate validate_aliases in plants/05_validate/run.py"
    assert "source_name" not in m.group(1), (
        "validate_aliases still references source_name (dropped from plant_aliases)"
    )
