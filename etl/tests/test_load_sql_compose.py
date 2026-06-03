"""reset_all_tables must execute a psycopg2.sql.Composed statement (safely
composed identifiers), not an f-string-built TRUNCATE."""
import importlib.util
import inspect
import os
from pathlib import Path

from psycopg2 import sql

# load.py reads DATABASE_URL at import (connect() is lazy); a dummy value lets us
# import the module without a live DB. No connection is opened by importing.
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost:5432/db")

_LOAD_PY = Path(__file__).resolve().parents[1] / "load" / "load.py"
_spec = importlib.util.spec_from_file_location("etl_load_mod", _LOAD_PY)
load = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load)


class _FakeCur:
    def __init__(self):
        self.executed = []

    def execute(self, query, *args):
        self.executed.append(query)


def test_reset_executes_composed_sql_not_string():
    cur = _FakeCur()
    load.reset_all_tables(cur)
    assert len(cur.executed) == 1
    # A safely-composed statement is a psycopg2.sql.Composed, never a raw str
    assert isinstance(cur.executed[0], sql.Composed)


def test_module_imports_psycopg2_sql():
    assert "from psycopg2 import sql" in inspect.getsource(load)
