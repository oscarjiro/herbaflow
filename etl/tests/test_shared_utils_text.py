# etl/tests/test_shared_utils_text.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.utils import clean_str, normalize_text, safe_str


def test_safe_str_does_not_fold_missing_markers():
    assert safe_str("unknown") == "unknown"
    assert safe_str("-") == "-"
    assert safe_str(None) == ""
    assert safe_str("  x  ") == "x"


def test_clean_str_folds_missing_markers():
    for token in ["", "na", "N/A", "none", "NULL", "nan", "-", "unknown", "unspecified"]:
        assert clean_str(token) == ""
    assert clean_str("  Aspirin  ") == "Aspirin"
    assert clean_str(None) == ""


def test_normalize_text_lowercases_collapses_and_folds():
    assert normalize_text("  Foo   Bar ") == "foo bar"
    assert normalize_text("Unknown") == ""
    assert normalize_text(None) == ""
