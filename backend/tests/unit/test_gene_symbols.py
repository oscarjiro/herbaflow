"""Unit tests for offline HGNC gene-symbol normalization."""
import pytest

import app.services.gene_symbols as gs


# Small fixture map mirroring the build script's nested structure:
# UPPER(key) -> {"symbol": approved, "kind": "approved"|"prev"|"alias"}
FIXTURE_MAP = {
    "TP53": {"symbol": "TP53", "kind": "approved"},
    "P53": {"symbol": "TP53", "kind": "prev"},
    "TNF": {"symbol": "TNF", "kind": "approved"},
    "TNFA": {"symbol": "TNF", "kind": "alias"},
    "TNFSF2": {"symbol": "TNF", "kind": "alias"},
}


@pytest.fixture(autouse=True)
def _reset_map():
    """Each test sets gs._MAP explicitly; restore to unloaded afterwards."""
    saved = gs._MAP
    gs._MAP = None
    yield
    gs._MAP = saved


def _use_fixture():
    gs._MAP = dict(FIXTURE_MAP)


def test_approved_symbol_passthrough():
    _use_fixture()
    r = gs.normalize("TP53")
    assert r.canonical == "TP53"
    assert r.status == "approved"


def test_alias_resolves_to_canonical():
    _use_fixture()
    r = gs.normalize("TNFA")
    assert r.canonical == "TNF"
    assert r.status == "alias_resolved"


def test_previous_symbol_resolves_to_canonical():
    _use_fixture()
    r = gs.normalize("P53")
    assert r.canonical == "TP53"
    assert r.status == "prev_resolved"


def test_case_insensitive():
    _use_fixture()
    r = gs.normalize("tnfa")
    assert r.canonical == "TNF"
    assert r.status == "alias_resolved"


def test_unknown_symbol_kept_and_flagged():
    _use_fixture()
    r = gs.normalize("ZZZ9")
    assert r.canonical == "ZZZ9"  # upcased, never dropped
    assert r.status == "unrecognized"


def test_blank_input_unrecognized_empty_canonical():
    _use_fixture()
    r = gs.normalize("   ")
    assert r.canonical == ""
    assert r.status == "unrecognized"


def test_normalize_many_preserves_order():
    _use_fixture()
    results = gs.normalize_many(["TNFA", "TP53", "ZZZ9"])
    assert [r.canonical for r in results] == ["TNF", "TP53", "ZZZ9"]
    assert [r.status for r in results] == ["alias_resolved", "approved", "unrecognized"]


def test_missing_map_file_degrades_to_identity(tmp_path):
    # Point the loader at a nonexistent file -> empty map -> everything unrecognized.
    gs._MAP = None
    missing = tmp_path / "nope.json.gz"
    loaded = gs._load_map(missing)
    assert loaded == {}
    gs._MAP = loaded
    r = gs.normalize("TNFA")
    assert r.canonical == "TNFA"
    assert r.status == "unrecognized"
