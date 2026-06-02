"""Guard: loader INSERT statements must not reference dropped columns.

Dropped columns:
- 4 alias loaders (plant, compound, disease, target): source_id, source_url
- load_targets: organism_tax_id
- load_compounds: lipinski_source
- load_plants: authorship, taxonomic_status, rank, gbif_*_key
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


def test_plants_insert_drops_trimmed_entity_columns():
    # load_plants must not insert the dropped plant entity columns.
    start = SRC.index("into plants (")
    block = SRC[start : start + 600]
    for col in ("authorship", "taxonomic_status", "rank", "gbif_usage_key",
                "gbif_accepted_usage_key", "gbif_species_key", "gbif_genus_key",
                "gbif_family_key", "gbif_kingdom_key"):
        assert col not in block, f"load_plants still inserts {col}"
    # over-keep guard: family_name and source columns remain
    assert "family_name" in block and "source_url" in block
