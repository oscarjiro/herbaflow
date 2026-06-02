"""Guard: loader INSERT statements must not reference dropped columns.

Dropped columns:
- 4 alias loaders (plant, compound, disease, target): source_id, source_url
- load_targets: organism_tax_id
- load_compounds: lipinski_source
"""
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "load" / "load.py").read_text(encoding="utf-8")

# Use lowercase markers — actual SQL in load.py uses lowercase "insert into ..."
ALIAS_MARKERS = (
    "into plant_aliases (",
    "into compound_aliases (",
    "into disease_aliases (",
    "into target_aliases (",
)


def test_alias_inserts_drop_source_columns():
    for marker in ALIAS_MARKERS:
        start = SRC.index(marker)
        block = SRC[start : start + 400]
        assert "source_id" not in block, f"{marker!r} block still inserts source_id"
        assert "source_url" not in block, f"{marker!r} block still inserts source_url"


def test_targets_insert_drops_organism_tax_id():
    # Use "into targets (" (with space+paren) to avoid matching "into target_aliases ("
    start = SRC.index("into targets (")
    block = SRC[start : start + 400]
    assert "organism_tax_id" not in block, "load_targets still inserts organism_tax_id"


def test_compounds_insert_drops_lipinski_source():
    start = SRC.index("into compounds (")
    block = SRC[start : start + 800]
    assert "lipinski_source" not in block, "load_compounds still inserts lipinski_source"
