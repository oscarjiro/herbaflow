# etl/tests/test_identity.py
import uuid
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared import identity


def test_namespaces_are_dns_v5_of_table_names():
    expect = {
        "PLANT_NS": "plants", "COMPOUND_NS": "compounds", "TARGET_NS": "targets",
        "DISEASE_NS": "diseases", "PLANT_ALIAS_NS": "plant_aliases",
        "COMPOUND_ALIAS_NS": "compound_aliases", "TARGET_ALIAS_NS": "target_aliases",
        "DISEASE_ALIAS_NS": "disease_aliases", "PLANT_COMPOUND_NS": "plant_compounds",
        "COMPOUND_TARGET_NS": "compound_targets", "DISEASE_TARGET_NS": "disease_targets",
    }
    for const, table in expect.items():
        assert getattr(identity, const) == uuid.uuid5(uuid.NAMESPACE_DNS, f"herbaflow.{table}")


def test_compound_target_ns_matches_backend_literal():
    # backend stage3_targets.COMPOUND_TARGET_NS literal — must not drift
    assert str(identity.COMPOUND_TARGET_NS) == "59a665ef-1743-5e45-98c2-128fe7e345a9"


def test_slugify():
    assert identity.slugify("  Type 2  Diabetes Mellitus! ") == "type_2_diabetes_mellitus"
    assert identity.slugify("Solanum lycopersicum L.") == "solanum_lycopersicum_l"
    assert identity.slugify("") == ""
