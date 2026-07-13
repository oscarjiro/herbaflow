"""Regression tests for the compounds/02_normalize `normalize_cas` wrapper.

The wrapper delegates per-comma-separated part to `shared.identity.normalize_cas`
but must preserve the pipeline's two-bucket reason taxonomy
(`checksum_failed` vs `invalid_format`) that `review_reasons` and the exported
`cas_validation_reason` column depend on.
"""

import importlib.util
import sys
from pathlib import Path

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))  # etl/


def _load(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ETL_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


normalize_run = _load("compounds_02_normalize", "compounds/02_normalize/run.py")


def test_checksum_failure_reason_preserved():
    # valid FORMAT, bad check digit -> checksum_failed (not invalid_format)
    _, is_valid, reason = normalize_run.normalize_cas("50-00-1")
    assert is_valid is False
    assert reason == "checksum_failed"


def test_format_garbage_reason():
    _, is_valid, reason = normalize_run.normalize_cas("not-a-cas")
    assert is_valid is False
    assert reason == "invalid_format"


def test_valid_cas_ok():
    normalized, is_valid, reason = normalize_run.normalize_cas("50-00-0")
    assert (normalized, is_valid, reason) == ("50-00-0", True, "ok")


def test_empty_missing():
    assert normalize_run.normalize_cas("") == ("", False, "missing")
