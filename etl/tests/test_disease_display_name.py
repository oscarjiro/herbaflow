"""disease_name is the case-preserved seed display; disease_name_clean stays normalized."""

import importlib.util  # noqa: E402
import sys
from pathlib import Path

import pandas as pd

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))

_RUN = ETL_ROOT / "diseases" / "03_build_canonical" / "run.py"
_spec = importlib.util.spec_from_file_location("build_canonical", _RUN)
build_canonical = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_canonical)


def _row(**kw):
    base = {
        "disease_name": "Type 2 Diabetes Mellitus",
        "disease_name_clean": "type 2 diabetes mellitus",
        "ontology_label": "type 2 diabetes mellitus",
        "standardized_name": "type 2 diabetes mellitus",
    }
    base.update(kw)
    return pd.Series(base)


def test_detect_seed_name_raw_preserves_case():
    assert build_canonical._detect_seed_name_raw(_row()) == "Type 2 Diabetes Mellitus"


def test_display_name_is_case_preserved_seed():
    row = _row()
    name, source = build_canonical._choose_display_name(row, confident=True)
    assert name == "Type 2 Diabetes Mellitus"
    assert source == "seed_disease_name"


def test_display_falls_back_to_label_case_when_no_seed():
    row = _row(disease_name="", seed_disease_name="", ontology_label="Ischemic Heart Disease")
    name, _ = build_canonical._choose_display_name(row, confident=True)
    assert name == "Ischemic Heart Disease"
