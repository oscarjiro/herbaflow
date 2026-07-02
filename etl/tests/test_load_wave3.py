"""Wave 3: the loader targets the trimmed schema (asserted against the source text)."""

from pathlib import Path

LOAD_SRC = (Path(__file__).resolve().parents[1] / "load" / "load.py").read_text(encoding="utf-8")
# Negative assertions run against the code only (the module docstring legitimately names the
# columns/tables it dropped, which would trip a naive substring check).
CODE = LOAD_SRC[LOAD_SRC.index("import argparse"):]


def test_loader_writes_trimmed_columns():
    # gbif_key is written; disease_targets writes opentargets_score not the stale `score`.
    assert "gbif_key" in LOAD_SRC
    assert "opentargets_score" in LOAD_SRC
    assert "association_type, score" not in LOAD_SRC
    # canonical_key survives ONLY as the read source for gbif_key, never as an inserted column.
    assert "insert into plants" in CODE
    assert "plant_id, canonical_key" not in CODE
    assert "compound_id, canonical_key" not in CODE
    # source_id is no longer inserted on any entity/junction.
    assert "source_id," not in CODE
    assert "source_id=" not in CODE


def test_alias_and_source_map_loaders_gone():
    for gone in (
        "def load_plant_aliases",
        "def load_compound_aliases",
        "def load_disease_aliases",
        "def load_target_aliases",
        "def load_source_map",
        "def resolve_src",
    ):
        assert gone not in LOAD_SRC, gone


def test_empty_natural_keys_written_as_null():
    # Empty inchi_key / uniprot_accession must be normalized to NULL (they are UNIQUE).
    assert "_blank_to_none" in LOAD_SRC


def test_reset_and_all_tables_drop_alias_and_source_tables():
    for gone in ("plant_aliases", "compound_aliases", "disease_aliases",
                 "target_aliases", "source_systems"):
        assert gone not in CODE, gone
