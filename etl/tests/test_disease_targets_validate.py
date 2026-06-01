"""Tests for disease_targets.04_validate score-range failure flagging.

Regression coverage: an out-of-range association score must cause the
validation stage to return a non-zero exit code, not exit 0 with a FAIL
result that is silently ignored.
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))  # etl/

_VALIDATE_PATH = ETL_ROOT / "disease_targets" / "04_validate" / "run.py"
_spec = importlib.util.spec_from_file_location("dt_04_validate", _VALIDATE_PATH)
validate_mod = importlib.util.module_from_spec(_spec)
sys.modules["dt_04_validate"] = validate_mod
_spec.loader.exec_module(validate_mod)


def _cfg():
    return {
        "logging": {"level": "WARNING"},
        "filtering": {
            "min_association_score": 0.1,
            "uniprot_coverage_warn_threshold": 0.0,
        },
        "validation": {"fail_on": []},
    }


def _write_minimal_canonical(canonical_dir: Path, diseases_csv: Path, score: str):
    """Write a minimal but schema-complete set of canonical CSVs."""
    targets = pd.DataFrame([{
        "target_id": "t1", "canonical_key": "uniprot:P31749",
        "gene_symbol": "AKT1", "protein_name": "RAC-alpha",
        "uniprot_accession": "P31749", "organism_tax_id": "9606",
        "source_name": "s1", "source_batch_id": "b1", "retrieved_at": "2026-01-01",
    }])
    aliases = pd.DataFrame([{
        "target_alias_id": "ta1", "target_id": "t1", "alias_name": "AKT1",
        "alias_key": "akt1", "alias_type": "symbol",
        "source_name": "s1", "source_batch_id": "b1", "retrieved_at": "2026-01-01",
    }])
    dts = pd.DataFrame([{
        "disease_target_id": "dt1", "disease_id": "d1", "target_id": "t1",
        "source_name": "s1", "association_type": "ot_overall", "score": score,
        "confidence": "0.9", "retrieved_at": "2026-01-01",
    }])
    diseases = pd.DataFrame([{"disease_id": "d1", "disease_name": "diabetes"}])

    targets.to_csv(canonical_dir / "targets.csv", index=False)
    aliases.to_csv(canonical_dir / "target_aliases.csv", index=False)
    dts.to_csv(canonical_dir / "disease_targets.csv", index=False)
    diseases.to_csv(diseases_csv, index=False)


def test_in_range_score_passes(tmp_path):
    canonical_dir = tmp_path / "canonical"
    out_dir = tmp_path / "out"
    canonical_dir.mkdir()
    diseases_csv = tmp_path / "diseases.csv"
    _write_minimal_canonical(canonical_dir, diseases_csv, score="0.85")

    rc = validate_mod.run(_cfg(), canonical_dir, diseases_csv, out_dir)
    assert rc == 0


def test_out_of_range_score_flags_failure(tmp_path):
    canonical_dir = tmp_path / "canonical"
    out_dir = tmp_path / "out"
    canonical_dir.mkdir()
    diseases_csv = tmp_path / "diseases.csv"
    # 1.5 is above the valid [min, 1.0] range — must trip has_fail.
    _write_minimal_canonical(canonical_dir, diseases_csv, score="1.5")

    rc = validate_mod.run(_cfg(), canonical_dir, diseases_csv, out_dir)
    assert rc == 1
