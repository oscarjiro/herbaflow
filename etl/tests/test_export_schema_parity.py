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


def test_plant_compounds_source_url_parity_across_stages():
    # 05_build_canonical emits a deep-link source_url on every plant_compound
    # row, and 06_validate + 07_export both require it. The three stages must
    # agree on the plant_compounds column set, or the source_url is silently
    # dropped at write time (DictWriter extrasaction="ignore") and 06's
    # ensure_columns fails on re-derive.
    stages = [
        "etl/compounds/05_build_canonical/run.py",
        "etl/compounds/06_validate/run.py",
        "etl/compounds/07_export/run.py",
    ]
    cols = [
        _extract_list_literal(
            pathlib.Path(p).read_text(encoding="utf-8"), "PLANT_COMPOUNDS_COLUMNS"
        )
        for p in stages
    ]
    for path, block in zip(stages, cols):
        assert "source_url" in block, f"{path} PLANT_COMPOUNDS_COLUMNS omits source_url"
    assert cols[0] == cols[1] == cols[2], f"plant_compounds columns diverge: {cols}"


def test_no_dead_columns_in_disease_targets_dicts():
    # disease_targets/03_build_canonical writes row dicts directly (no column
    # constant); assert none of the emitted dict keys are dead columns.
    text = pathlib.Path(
        "etl/disease_targets/03_build_canonical/run.py"
    ).read_text(encoding="utf-8")
    for col in DEAD:
        assert f'"{col}":' not in text, f"disease_targets build still emits {col}"
