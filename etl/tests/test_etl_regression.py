"""Regression tests for assorted ETL correctness fixes.

Covers:
- diseases/03_build_canonical `_split_multivalue` returns [] (not "") on empty
  input, matching its `-> list[str]` contract.
- compounds/06_validate `load_optional_plant_ids` does not raise
  UnboundLocalError when the optional plant export file is missing.
- knapsack/main boolean CLI flags parse to real booleans and support
  the --no-<flag> form (BooleanOptionalAction), so "--resume False" can no
  longer store a truthy string.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import logging

import pytest

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))  # etl/


def _load(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ETL_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass introspection (KW_ONLY lookup via
    # sys.modules[cls.__module__]) resolves while the module body runs.
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


diseases_canonical = _load(
    "diseases_03_build_canonical", "diseases/03_build_canonical/run.py"
)
compounds_validate = _load(
    "compounds_06_validate", "compounds/06_validate/run.py"
)
knapsack_main = _load("knapsack_main", "knapsack/main.py")


class TestSplitMultivalue:
    def test_empty_returns_empty_list(self):
        assert diseases_canonical._split_multivalue("") == []

    def test_none_returns_empty_list(self):
        assert diseases_canonical._split_multivalue(None) == []

    def test_whitespace_returns_empty_list(self):
        assert diseases_canonical._split_multivalue("   ") == []

    def test_single_value(self):
        assert diseases_canonical._split_multivalue("foo") == ["foo"]

    def test_multivalue_split(self):
        result = diseases_canonical._split_multivalue("a; b, c")
        assert result == ["a", "b", "c"]


class TestLoadOptionalPlantIds:
    def test_missing_plant_export_does_not_raise(self, tmp_path):
        settings = SimpleNamespace(
            plant_export_csv=tmp_path / "does_not_exist.csv"
        )
        logger = logging.getLogger("test_load_optional_plant_ids")
        plant_ids, loaded = compounds_validate.load_optional_plant_ids(
            settings, logger
        )
        assert plant_ids == set()
        assert loaded is False

    def test_none_plant_export_does_not_raise(self, tmp_path):
        settings = SimpleNamespace(plant_export_csv=None)
        logger = logging.getLogger("test_load_optional_plant_ids")
        plant_ids, loaded = compounds_validate.load_optional_plant_ids(
            settings, logger
        )
        assert plant_ids == set()
        assert loaded is False

    def test_present_plant_export_loads_ids(self, tmp_path):
        export = tmp_path / "plants.csv"
        export.write_text("plant_id\np1\np2\n\n", encoding="utf-8")
        settings = SimpleNamespace(plant_export_csv=export)
        logger = logging.getLogger("test_load_optional_plant_ids")
        plant_ids, loaded = compounds_validate.load_optional_plant_ids(
            settings, logger
        )
        assert plant_ids == {"p1", "p2"}
        assert loaded is True


class TestKnapsackBooleanFlags:
    def _parse(self, argv):
        old = sys.argv
        try:
            sys.argv = ["main.py"] + argv
            return knapsack_main.parse_args()
        finally:
            sys.argv = old

    def test_defaults(self):
        args = self._parse([])
        assert args.resume is False
        assert args.require_detail_url is True

    def test_resume_flag(self):
        args = self._parse(["--resume"])
        assert args.resume is True

    def test_no_resume_flag(self):
        args = self._parse(["--no-resume"])
        assert args.resume is False

    def test_no_require_detail_url(self):
        args = self._parse(["--no-require-detail-url"])
        assert args.require_detail_url is False

    def test_flags_are_real_booleans(self):
        args = self._parse(["--resume"])
        assert isinstance(args.resume, bool)
        assert isinstance(args.require_detail_url, bool)
