# etl/tests/test_compounds_properties.py
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
spec = importlib.util.spec_from_file_location(
    "enrich_properties",
    Path(__file__).resolve().parents[1] / "compounds" / "04_enrich" / "properties.py",
)
props = importlib.util.module_from_spec(spec)
spec.loader.exec_module(props)


def test_rdkit_descriptors_for_aspirin():
    d = props.rdkit_descriptors("CC(=O)Oc1ccccc1C(=O)O")  # aspirin
    assert d is not None
    assert 179.0 < float(d["molecular_weight"]) < 181.0
    assert int(d["hbond_donors"]) == 1
    assert int(d["hbond_acceptors"]) == 3


def test_rdkit_descriptors_bad_smiles_returns_none():
    assert props.rdkit_descriptors("not a smiles!!!") is None
