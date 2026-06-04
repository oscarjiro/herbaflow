# etl/tests/test_frames.py
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.frames import read_frame, validate_required_columns, write_frame


def test_write_then_read_frame_roundtrips_as_strings(tmp_path):
    df = pd.DataFrame({"a": ["1", "x"], "b": ["", "NA"]})
    p = tmp_path / "t.csv"
    write_frame(df, p)
    out = read_frame(p)
    # dtype=str, keep_default_na=False, na_values=[] => no NaN coercion
    assert out["b"].tolist() == ["", "NA"]
    assert out["a"].tolist() == ["1", "x"]


def test_write_frame_creates_parent_dirs(tmp_path):
    df = pd.DataFrame({"a": ["1"]})
    p = tmp_path / "nested" / "deep" / "t.csv"
    write_frame(df, p)
    assert p.exists()


def test_write_frame_no_index_column(tmp_path):
    df = pd.DataFrame({"a": ["1", "2"]})
    p = tmp_path / "t.csv"
    write_frame(df, p)
    assert p.read_text(encoding="utf-8").splitlines()[0] == "a"


def test_validate_required_columns_raises_on_missing():
    df = pd.DataFrame({"a": ["1"]})
    with pytest.raises(ValueError, match="missing required columns: b"):
        validate_required_columns(df, ["a", "b"], table_name="t")


def test_validate_required_columns_passes_when_present():
    df = pd.DataFrame({"a": ["1"], "b": ["2"]})
    validate_required_columns(df, ["a", "b"])  # no raise
