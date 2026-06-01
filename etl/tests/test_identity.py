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


def test_plant_canonical_key_cascade():
    assert identity.plant_canonical_key("3190652", "solanum lycopersicum l") == "gbif:3190652"
    assert identity.plant_canonical_key("", "Solanum lycopersicum L.") == "plant:solanum_lycopersicum_l"


def test_compound_canonical_key_single_colon_cascade():
    f = identity.compound_canonical_key
    assert f({"inchi_key": "abc"}) == "inchikey:ABC"
    assert f({"pubchem_cid": "678"}) == "pubchem:678"
    assert f({"chembl_id": "CHEMBL25"}) == "chembl:CHEMBL25"
    assert f({"representative_cas_id": "50-00-0"}).startswith("cas:")
    assert f({"preferred_name": "Foo", "molecular_formula": "C2H6O"}) == "name_formula:foo:c2h6o"
    assert f({"preferred_name": "Foo"}) == "name:foo"
    assert f({"molecular_formula": "C2H6O"}) == "formula:c2h6o"
    assert f({}) == ""
    # priority: inchi_key wins over everything
    assert f({"inchi_key": "abc", "pubchem_cid": "678"}) == "inchikey:ABC"


def test_target_canonical_key_cascade_and_isoform_fold():
    assert identity.target_canonical_key(uniprot="P04637") == "uniprot:P04637"
    assert identity.target_canonical_key(uniprot="P04637-2") == "uniprot:P04637"  # isoform folded
    assert identity.target_canonical_key(ensembl="ENSG00000141510") == "ensembl:ENSG00000141510"
    assert identity.target_canonical_key(gene="tp53") == "gene:TP53"


def test_disease_canonical_key_curie_cascade():
    f = identity.disease_canonical_key
    assert f("Disease Ontology", "DOID_9352", "type_2_diabetes_mellitus") == "doid:9352"
    assert f("Disease Ontology", "DOID_0080208", "masld") == "doid:0080208"
    assert f("MeSH", "D001234", "x") == "mesh:D001234"
    assert f("", "", "Type 2 Diabetes Mellitus") == "disease:type_2_diabetes_mellitus"


def test_entity_ids_are_v5_of_canonical_key():
    assert identity.plant_id("3190652") == identity._v5(identity.PLANT_NS, "gbif:3190652")
    assert identity.compound_id({"inchi_key": "abc"}) == identity._v5(identity.COMPOUND_NS, "inchikey:ABC")
    assert identity.target_id(uniprot="P04637") == identity._v5(identity.TARGET_NS, "uniprot:P04637")
    assert identity.disease_id("Disease Ontology", "DOID_9352", "x") == \
        identity._v5(identity.DISEASE_NS, "doid:9352")


def test_alias_ids_key_on_parent_and_slug_only():
    pid = "11111111-1111-5111-8111-111111111111"
    assert identity.plant_alias_id(pid, "solanum") == identity._v5(identity.PLANT_ALIAS_NS, f"{pid}:solanum")
    assert identity.compound_alias_id(pid, "aspirin") == identity._v5(identity.COMPOUND_ALIAS_NS, f"{pid}:aspirin")
    assert identity.target_alias_id(pid, "tp53") == identity._v5(identity.TARGET_ALIAS_NS, f"{pid}:tp53")
    assert identity.disease_alias_id(pid, "t2dm") == identity._v5(identity.DISEASE_ALIAS_NS, f"{pid}:t2dm")


def test_alias_priority_pick_keeps_highest():
    # higher-priority type wins on a slug collision
    chosen = identity.pick_alias(
        current={"alias_type": "ontology_synonym"},
        candidate={"alias_type": "canonical_name"},
    )
    assert chosen["alias_type"] == "canonical_name"
    # lower-priority candidate does NOT replace current (replace only on strictly greater)
    keep = identity.pick_alias(
        current={"alias_type": "canonical_name"},
        candidate={"alias_type": "raw_name"},
    )
    assert keep["alias_type"] == "canonical_name"
    # None current -> candidate
    assert identity.pick_alias(None, {"alias_type": "raw_name"})["alias_type"] == "raw_name"


def test_bridge_ids_pair_grain_single_colon_no_source():
    p = "aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa"
    c = "bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb"
    t = "cccccccc-cccc-5ccc-8ccc-cccccccccccc"
    d = "dddddddd-dddd-5ddd-8ddd-dddddddddddd"
    assert identity.plant_compound_id(p, c) == identity._v5(identity.PLANT_COMPOUND_NS, f"{p}:{c}")
    assert identity.compound_target_id(c, t) == identity._v5(identity.COMPOUND_TARGET_NS, f"{c}:{t}")
    assert identity.disease_target_id(d, t) == identity._v5(identity.DISEASE_TARGET_NS, f"{d}:{t}")
    # no 'cmppl_' prefix, no source component
    assert not identity.plant_compound_id(p, c).startswith("cmppl_")
