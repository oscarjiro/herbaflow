"""Guard: trimmed columns must not appear in entity output column lists.

Plants: dropped gbif_*_key + authorship + taxonomic_status + rank
Targets: dropped organism_tax_id
Compounds: dropped lipinski_source (build and export)

Approach mirrors test_alias_outputs_no_source.py — source-scan the relevant
run.py files and extract the column-list constant literals, then assert the
banned names are absent.
"""
import importlib.util
import pathlib
import re
import sys

ETL = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Plants — module import (matches the pattern that works for prior plant tests)
# ---------------------------------------------------------------------------
def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ETL / rel)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


plants = _load("plants/04_build_canonical/run_part2.py", "p2")

PLANTS_DROPPED = {
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


def test_plants_output_drops_trimmed_columns():
    assert PLANTS_DROPPED.isdisjoint(plants.PLANTS_OUTPUT_COLUMNS), (
        f"PLANTS_OUTPUT_COLUMNS still contains: {PLANTS_DROPPED & set(plants.PLANTS_OUTPUT_COLUMNS)}"
    )


def test_plants_output_keeps_family_name():
    assert "family_name" in plants.PLANTS_OUTPUT_COLUMNS


def test_plants_output_keeps_source_name():
    assert "source_name" in plants.PLANTS_OUTPUT_COLUMNS


# ---------------------------------------------------------------------------
# Targets — source-scan 03_build_canonical/run.py for the row dict
# ---------------------------------------------------------------------------
def _extract_list_literal(text: str, name: str) -> set:
    m = re.search(rf"{re.escape(name)}\s*=\s*\[([^\]]*)\]", text, re.DOTALL)
    assert m, f"Could not find {name} in source"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def _build_targets_row_keys(text: str) -> set:
    """Extract dict keys from the rows.append({...}) block in build_targets."""
    m = re.search(r"def build_targets\b(.+?)(?=\ndef |\Z)", text, re.DOTALL)
    assert m, "Could not find build_targets in disease_targets/03_build_canonical/run.py"
    return set(re.findall(r'"([^"]+)":', m.group(1)))


def test_targets_build_row_drops_organism_tax_id():
    text = (ETL / "disease_targets/03_build_canonical/run.py").read_text(encoding="utf-8")
    keys = _build_targets_row_keys(text)
    assert "organism_tax_id" not in keys, (
        "build_targets still emits organism_tax_id into the row dict"
    )


# ---------------------------------------------------------------------------
# Compounds — source-scan both build (05) and export (07) COMPOUNDS_COLUMNS
# ---------------------------------------------------------------------------
def test_compounds_build_drops_lipinski_source():
    text = (ETL / "compounds/05_build_canonical/run.py").read_text(encoding="utf-8")
    cols = _extract_list_literal(text, "COMPOUNDS_COLUMNS")
    assert "lipinski_source" not in cols, (
        "compounds/05_build_canonical COMPOUNDS_COLUMNS still lists lipinski_source"
    )


def test_compounds_export_drops_lipinski_source():
    text = (ETL / "compounds/07_export/run.py").read_text(encoding="utf-8")
    cols = _extract_list_literal(text, "COMPOUNDS_COLUMNS")
    assert "lipinski_source" not in cols, (
        "compounds/07_export COMPOUNDS_COLUMNS still lists lipinski_source"
    )
