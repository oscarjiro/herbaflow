"""Guard: none of the 4 alias output column lists may carry source_id/source_url/source_name.

All four modules are checked by source-scanning the relevant run.py file and extracting
the alias column-list constant, asserting none of the banned names appear in it.
Targets additionally scans the build_target_aliases function body for banned dict keys.
"""
import pathlib
import re

ETL = pathlib.Path(__file__).resolve().parents[1]

BANNED = {"source_id", "source_url", "source_name"}


def _alias_column_block(text: str, constant_name: str) -> set[str]:
    """Extract string literals from a named list constant in source text."""
    m = re.search(rf"{re.escape(constant_name)}\s*=\s*\[([^\]]*)\]", text, re.DOTALL)
    assert m, f"Could not find {constant_name} in source"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def test_plant_build_alias_columns_have_no_source():
    text = (ETL / "plants/04_build_canonical/run_part2.py").read_text(encoding="utf-8")
    cols = _alias_column_block(text, "ALIASES_OUTPUT_COLUMNS")
    assert BANNED.isdisjoint(cols), (
        f"plants/04_build_canonical ALIASES_OUTPUT_COLUMNS still has: {BANNED & cols}"
    )


def test_plant_export_alias_columns_have_no_source():
    text = (ETL / "plants/06_export/run.py").read_text(encoding="utf-8")
    cols = _alias_column_block(text, "ALIASES_SCHEMA_COLUMNS")
    assert BANNED.isdisjoint(cols), (
        f"plants/06_export ALIASES_SCHEMA_COLUMNS still has: {BANNED & cols}"
    )


def test_disease_alias_columns_have_no_source():
    text = (ETL / "diseases/03_build_canonical/run.py").read_text(encoding="utf-8")
    cols = _alias_column_block(text, "ALIAS_OUTPUT_COLUMNS")
    assert BANNED.isdisjoint(cols), (
        f"diseases/03_build_canonical ALIAS_OUTPUT_COLUMNS still has: {BANNED & cols}"
    )


def test_compounds_build_alias_columns_have_no_source():
    text = (ETL / "compounds/05_build_canonical/run.py").read_text(encoding="utf-8")
    cols = _alias_column_block(text, "ALIASES_COLUMNS")
    assert BANNED.isdisjoint(cols), (
        f"compounds/05_build_canonical ALIASES_COLUMNS still has: {BANNED & cols}"
    )


def test_compounds_export_alias_columns_have_no_source():
    text = (ETL / "compounds/07_export/run.py").read_text(encoding="utf-8")
    cols = _alias_column_block(text, "ALIASES_COLUMNS")
    assert BANNED.isdisjoint(cols), (
        f"compounds/07_export ALIASES_COLUMNS still has: {BANNED & cols}"
    )


def test_targets_alias_row_dict_has_no_source():
    text = (ETL / "disease_targets/03_build_canonical/run.py").read_text(encoding="utf-8")
    # build_target_aliases builds dicts inline; scan that function's body only.
    # Check that none of the banned names appear as dict keys (i.e. "col": pattern),
    # not as .get("col") input reads.
    m = re.search(r"def build_target_aliases\b(.+?)(?=\ndef |\Z)", text, re.DOTALL)
    assert m, "Could not find build_target_aliases in disease_targets/03_build_canonical/run.py"
    fn_text = m.group(1)
    for col in BANNED:
        assert f'"{col}":' not in fn_text, (
            f'build_target_aliases still emits "{col}": key in a returned dict'
        )
