"""Unit tests for plants/utils.py, compounds/utils.py, diseases/utils.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uuid
import pytest
from plants.utils import (
    split_scientific_name,
    build_canonical_lookup_key,
    plant_id,
    alias_id,
    PLANT_NS,
    PLANT_ALIAS_NS,
)


def test_split_scientific_name_with_authorship():
    canonical, authorship = split_scientific_name("Curcuma longa L.")
    assert canonical == "Curcuma longa"
    assert authorship == "L."

def test_split_scientific_name_without_authorship():
    canonical, authorship = split_scientific_name("Curcuma longa")
    assert canonical == "Curcuma longa"
    assert authorship == ""

def test_split_scientific_name_single_word():
    canonical, authorship = split_scientific_name("Zingiber")
    assert canonical == "Zingiber"
    assert authorship == ""

def test_build_canonical_lookup_key_lowercases():
    assert build_canonical_lookup_key("Curcuma Longa") == "curcuma longa"

def test_build_canonical_lookup_key_strips():
    assert build_canonical_lookup_key("  Curcuma longa  ") == "curcuma longa"

def test_plant_id_deterministic():
    assert plant_id("12345") == plant_id("12345")

def test_plant_id_valid_uuid():
    uuid.UUID(plant_id("12345"))

def test_plant_id_different_keys_differ():
    assert plant_id("12345") != plant_id("99999")

def test_alias_id_deterministic():
    pid = plant_id("12345")
    assert alias_id(pid, "synonym", "Turmeric") == alias_id(pid, "synonym", "Turmeric")

def test_alias_id_different_types_differ():
    pid = plant_id("12345")
    assert alias_id(pid, "synonym", "X") != alias_id(pid, "common_name", "X")

def test_plant_ns_is_uuid():
    uuid.UUID(str(PLANT_NS))

def test_plant_alias_ns_differs_from_plant_ns():
    assert PLANT_NS != PLANT_ALIAS_NS


from compounds.utils import (
    normalize_cas,
    compound_id,
    compound_alias_id,
    COMPOUND_NS,
)


def test_normalize_cas_valid():
    normalized, is_valid, _ = normalize_cas("50-00-0")
    assert normalized == "50-00-0"
    assert is_valid is True

def test_normalize_cas_invalid_checksum():
    _, is_valid, reason = normalize_cas("50-00-1")
    assert is_valid is False
    assert "checksum" in reason.lower()

def test_normalize_cas_empty():
    normalized, is_valid, _ = normalize_cas("")
    assert normalized == ""
    assert is_valid is False

def test_compound_id_deterministic():
    assert compound_id("INCHIKEY123") == compound_id("INCHIKEY123")

def test_compound_id_valid_uuid():
    uuid.UUID(compound_id("INCHIKEY123"))

def test_compound_alias_id_deterministic():
    cid = compound_id("INCHIKEY123")
    assert compound_alias_id(cid, "Curcumin") == compound_alias_id(cid, "Curcumin")

def test_compound_ns_differs_from_plant_ns():
    assert COMPOUND_NS != PLANT_NS


from diseases.utils import (
    disease_id,
    canonical_key as disease_canonical_key,
    DISEASE_NS,
)


def test_disease_id_deterministic():
    assert disease_id("DOID:9352") == disease_id("DOID:9352")

def test_disease_id_valid_uuid():
    uuid.UUID(disease_id("DOID:9352"))

def test_disease_ns_differs_from_plant_ns():
    assert DISEASE_NS != PLANT_NS

def test_disease_canonical_key_lowercases():
    key = disease_canonical_key("Type 2 Diabetes Mellitus")
    assert key == key.lower()
