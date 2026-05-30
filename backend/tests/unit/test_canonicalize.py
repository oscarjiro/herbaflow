import uuid

from app.services.canonicalize import (
    COMPOUND_NS,
    TARGET_NS,
    compound_canonical_key,
    make_compound_id,
    fold_isoform,
    target_canonical_key,
    make_target_id,
)


def test_namespaces_match_etl_derivation():
    assert COMPOUND_NS == uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.compounds")
    assert TARGET_NS == uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.targets")
    assert str(COMPOUND_NS) == "ea972261-ef25-5420-b17c-317f73ec590e"
    assert str(TARGET_NS) == "421e4557-e00d-533d-ab26-5f7b761b9483"


def test_compound_canonical_key_form_and_normalization():
    assert compound_canonical_key("REFJWTPEDVJJIY-UHFFFAOYSA-N") == "inchi::REFJWTPEDVJJIY-UHFFFAOYSA-N"
    assert compound_canonical_key("  refjwtpedvjjiy-uhfffaoysa-n ") == "inchi::REFJWTPEDVJJIY-UHFFFAOYSA-N"


def test_compound_id_matches_etl_fixture():
    assert make_compound_id("REFJWTPEDVJJIY-UHFFFAOYSA-N") == "7373585f-6e71-532a-8e3e-330defb8fbe8"


def test_fold_isoform():
    assert fold_isoform("P04637-2") == "P04637"
    assert fold_isoform("P04637") == "P04637"
    assert fold_isoform("  p04637 ") == "P04637"
    assert fold_isoform("A0A024R161") == "A0A024R161"


def test_target_canonical_key_and_id_fixture():
    assert target_canonical_key("P04637") == "uniprot:P04637"
    assert target_canonical_key("P04637-2") == "uniprot:P04637"
    assert make_target_id("P04637") == "9c4b3fe6-955c-5daf-8717-0e254a7ff9da"
    assert make_target_id("P04637-2") == "9c4b3fe6-955c-5daf-8717-0e254a7ff9da"
    # lowercase isoform input must normalize (upper) AND fold to the parent id
    assert target_canonical_key("p04637-2") == "uniprot:P04637"
    assert make_target_id("p04637-2") == "9c4b3fe6-955c-5daf-8717-0e254a7ff9da"
