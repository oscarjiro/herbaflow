"""
AF-2: etl/load/load.py must be importable without DATABASE_URL set.

Tests:
  1. test_module_imports_without_database_url — mandatory: import with env var absent
     and load_dotenv patched out (simulates CI with no .env file).
  2. test_conflict_do_nothing — _conflict with upsert=False returns DO NOTHING clause.
  3. test_conflict_do_update — _conflict with upsert=True returns DO UPDATE SET clause.
"""
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

_LOAD_PY = Path(__file__).resolve().parents[1] / "load" / "load.py"


def _load_module_no_env():
    """Load load.py with DATABASE_URL absent and load_dotenv patched to a no-op."""
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    # patch both the env AND load_dotenv so the .env file cannot backfill the var
    with patch.dict(os.environ, env, clear=True), \
         patch("dotenv.load_dotenv", return_value=False):
        spec = importlib.util.spec_from_file_location("etl_load_mod_logic_bare", _LOAD_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def _load_module():
    """Load load.py normally (DATABASE_URL may or may not be set)."""
    spec = importlib.util.spec_from_file_location("etl_load_mod_logic", _LOAD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_module_imports_without_database_url():
    """load.py must be importable when DATABASE_URL is absent (no env, no .env file)."""
    mod = _load_module_no_env()
    assert hasattr(mod, "connect")


def test_conflict_do_nothing():
    mod = _load_module()
    result = mod._conflict("plant_id", ["canonical_key", "source_id"], upsert=False)
    assert result == "on conflict (plant_id) do nothing"


def test_conflict_do_update():
    mod = _load_module()
    result = mod._conflict("plant_id", ["gbif_key", "source_url"], upsert=True)
    assert result == (
        "on conflict (plant_id) do update set "
        "gbif_key = excluded.gbif_key, source_url = excluded.source_url"
    )
