"""Every loaded final-export CSV must be free of the S3/S4 dead columns.

Single consolidated guard tying the 10 loaded ETL outputs to the post-S3/S4
trimmed DB schema (`source_batch_id`, `confidence`, `evidence_type`,
`source_plant_raw_id`, `source_compound_raw_id` were all dropped). The
constant-driven modules (plants, compounds, diseases) are checked by extracting
their export column-list literals; disease_targets writes its row dicts
directly, so it is checked by the absence of the dead dict keys.
"""
import pathlib
import re

DEAD = {
    "source_batch_id",
    "confidence",
    "evidence_type",
    "source_plant_raw_id",
    "source_compound_raw_id",
}

# (constant name, file) for the column-list-driven loaded exports.
LOADED_EXPORT_CONSTANTS = [
    ("PLANTS_SCHEMA_COLUMNS", "etl/plants/06_export/run.py"),
    ("ALIASES_SCHEMA_COLUMNS", "etl/plants/06_export/run.py"),
    ("COMPOUNDS_COLUMNS", "etl/compounds/07_export/run.py"),
    ("ALIASES_COLUMNS", "etl/compounds/07_export/run.py"),
    ("PLANT_COMPOUNDS_COLUMNS", "etl/compounds/07_export/run.py"),
    ("DISEASE_OUTPUT_COLUMNS", "etl/diseases/03_build_canonical/run.py"),
    ("ALIAS_OUTPUT_COLUMNS", "etl/diseases/03_build_canonical/run.py"),
]


def _extract_list_literal(text: str, name: str) -> set[str]:
    start = text.index(f"{name} = [")
    end = text.index("]", start)
    return set(re.findall(r'"([^"]+)"', text[start:end]))


def test_no_dead_columns_in_loaded_export_constants():
    for name, path in LOADED_EXPORT_CONSTANTS:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        block = _extract_list_literal(text, name)
        assert DEAD.isdisjoint(block), f"{name} in {path} still lists {DEAD & block}"


def test_no_dead_columns_in_disease_targets_dicts():
    # disease_targets/03_build_canonical writes row dicts directly (no column
    # constant); assert none of the emitted dict keys are dead columns.
    text = pathlib.Path(
        "etl/disease_targets/03_build_canonical/run.py"
    ).read_text(encoding="utf-8")
    for col in DEAD:
        assert f'"{col}":' not in text, f"disease_targets build still emits {col}"
