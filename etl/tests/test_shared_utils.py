"""Unit tests for etl/shared/utils.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uuid
from shared.utils import (
    normalize_whitespace,
    normalize_unicode,
    to_key,
    safe_str,
    stable_id,
    now_iso,
    make_run_id,
    ensure_dir,
    read_csv,
    write_csv,
    write_json,
    load_settings,
    setup_logging,
    ETL_ROOT,
)


def test_normalize_whitespace_trims_and_collapses():
    assert normalize_whitespace("  foo   bar  ") == "foo bar"

def test_normalize_whitespace_empty():
    assert normalize_whitespace("") == ""

def test_normalize_whitespace_none_safe():
    assert normalize_whitespace(None) == ""

def test_normalize_unicode_nfkc():
    assert normalize_unicode("ﬁ") == "fi"  # ﬁ ligature → fi

def test_normalize_unicode_empty():
    assert normalize_unicode("") == ""

def test_to_key_lowercases_and_strips_punctuation():
    assert to_key("Curcuma longa (L.)") == "curcuma_longa_l"

def test_to_key_collapses_spaces():
    assert to_key("  hello   world  ") == "hello_world"

def test_to_key_empty():
    assert to_key("") == ""

def test_safe_str_none_returns_empty():
    assert safe_str(None) == ""

def test_safe_str_strips():
    assert safe_str("  hello  ") == "hello"

def test_safe_str_numeric():
    assert safe_str(42) == "42"

def test_stable_id_is_deterministic():
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.test")
    assert stable_id(ns, "abc") == stable_id(ns, "abc")

def test_stable_id_different_inputs_differ():
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.test")
    assert stable_id(ns, "abc") != stable_id(ns, "xyz")

def test_stable_id_is_valid_uuid():
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.test")
    result = stable_id(ns, "abc")
    uuid.UUID(result)  # raises if invalid

def test_now_iso_returns_string():
    result = now_iso()
    assert isinstance(result, str)
    assert "T" in result

def test_make_run_id_contains_prefix():
    result = make_run_id("plants")
    assert result.startswith("plants_")

def test_ensure_dir_creates_directory(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    ensure_dir(target)
    assert target.is_dir()

def test_write_and_read_csv(tmp_path):
    path = tmp_path / "test.csv"
    rows = [{"name": "Curcuma", "id": "1"}, {"name": "Zingiber", "id": "2"}]
    write_csv(rows, path, fieldnames=["name", "id"])
    result = read_csv(path)
    assert result == rows

def test_write_csv_empty_with_fieldnames_writes_header(tmp_path):
    # Empty rows + explicit fieldnames must still emit the header so downstream
    # DictReader-based stages don't choke on a missing-header file.
    path = tmp_path / "empty.csv"
    write_csv([], path, fieldnames=["name", "id"])
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ["name,id"]


def test_write_csv_empty_without_fieldnames_is_blank(tmp_path):
    # No rows and no fieldnames: columns are unknowable, so a blank file stays blank.
    path = tmp_path / "blank.csv"
    write_csv([], path)
    assert path.read_text(encoding="utf-8") == ""

def test_write_json(tmp_path):
    import json
    path = tmp_path / "data.json"
    write_json({"key": "value"}, path)
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == {"key": "value"}

def test_etl_root_points_to_etl():
    assert ETL_ROOT.name == "etl"
    assert (ETL_ROOT / "shared").is_dir()


def test_load_settings_returns_merged_dict(tmp_path, monkeypatch):
    etl_tmp = tmp_path / "etl"
    shared_dir = etl_tmp / "shared"
    module_dir = etl_tmp / "testmodule"
    shared_dir.mkdir(parents=True)
    module_dir.mkdir(parents=True)
    (shared_dir / "__init__.py").write_text("")
    (shared_dir / "settings.yml").write_text("logging:\n  level: INFO\nruntime:\n  stop_on_error: true\n")
    (module_dir / "settings.yml").write_text("module:\n  name: testmodule\npaths:\n  out: testmodule/out\n")

    import shared.utils as su
    monkeypatch.setattr(su, "ETL_ROOT", etl_tmp)
    cfg = su.load_settings("testmodule")
    assert cfg["module"]["name"] == "testmodule"
    assert cfg["logging"]["level"] == "INFO"  # from shared
    assert cfg["paths"]["out"] == "testmodule/out"  # from module


def test_setup_logging_returns_logger():
    from shared.utils import setup_logging
    import logging
    cfg = {"logging": {"level": "WARNING", "format": "%(message)s"}}
    logger = setup_logging("test.logger", cfg)
    assert isinstance(logger, logging.Logger)
    assert logger.level == logging.WARNING
