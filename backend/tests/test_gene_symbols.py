from app.services import gene_symbols


def test_approved_symbol_passes_through():
    r = gene_symbols.normalize("TP53")
    assert r.canonical == "TP53"
    assert r.status in {"approved", "unrecognized"}


def test_blank_is_unrecognized():
    r = gene_symbols.normalize("   ")
    assert r.canonical == ""
    assert r.status == "unrecognized"


def test_unknown_symbol_upcased_and_flagged():
    r = gene_symbols.normalize("notagene")
    assert r.canonical == "NOTAGENE"
    assert r.status == "unrecognized"


def test_missing_map_degrades_to_identity(monkeypatch):
    from pathlib import Path

    monkeypatch.setattr(gene_symbols, "_MAP", None)
    monkeypatch.setattr(gene_symbols, "_MAP_PATH", Path("/does/not/exist.json.gz"))
    r = gene_symbols.normalize("BRCA1")
    assert r.canonical == "BRCA1"
    assert r.status == "unrecognized"
