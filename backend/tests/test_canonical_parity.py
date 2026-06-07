"""app/services/canonical.py must produce byte-identical ids to etl/shared/identity.py.

The ETL module is stdlib-only, so we load it by path and compare every public builder.
This guards the deliberate twin against drift (reproducibility evidence).
"""

import importlib.util
from pathlib import Path

from app.services import canonical as be

_ETL_IDENTITY = Path(__file__).resolve().parents[2] / "etl" / "shared" / "identity.py"


def _load_etl_identity():
    spec = importlib.util.spec_from_file_location("etl_identity", _ETL_IDENTITY)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


etl = _load_etl_identity()

_COMPOUND = {"inchi_key": "RYYVLZVUVIJVGH-UHFFFAOYSA-N"}


def test_slugify_matches():
    for v in ["Type 2 Diabetes Mellitus", "  Foo/Bar  ", "Curcuma longa"]:
        assert be.slugify(v) == etl.slugify(v)


def test_canonical_keys_match():
    assert be.plant_canonical_key("3034234", "x") == etl.plant_canonical_key("3034234", "x")
    assert be.compound_canonical_key(_COMPOUND) == etl.compound_canonical_key(_COMPOUND)
    assert be.target_canonical_key(uniprot="P04637-2") == etl.target_canonical_key(
        uniprot="P04637-2"
    )
    be_disease = be.disease_canonical_key("Disease Ontology", "DOID_9352", "x")
    etl_disease = etl.disease_canonical_key("Disease Ontology", "DOID_9352", "x")
    assert be_disease == etl_disease


def test_entity_ids_match():
    assert be.plant_id("3034234") == etl.plant_id("3034234")
    assert be.compound_id(_COMPOUND) == etl.compound_id(_COMPOUND)
    assert be.target_id(uniprot="P04637") == etl.target_id(uniprot="P04637")
    be_disease = be.disease_id("Disease Ontology", "DOID_9352", "x")
    etl_disease = etl.disease_id("Disease Ontology", "DOID_9352", "x")
    assert be_disease == etl_disease


def test_alias_and_bridge_ids_match():
    pid = be.plant_id("3034234")
    assert be.plant_alias_id(pid, "alias") == etl.plant_alias_id(pid, "alias")
    cid = be.compound_id(_COMPOUND)
    tid = be.target_id(uniprot="P04637")
    assert be.compound_target_id(cid, tid) == etl.compound_target_id(cid, tid)


def test_namespaces_match():
    for name in ["PLANT_NS", "COMPOUND_NS", "TARGET_NS", "DISEASE_NS", "DISEASE_TARGET_NS"]:
        assert getattr(be, name) == getattr(etl, name)
