from pathlib import Path

LOAD_PY = Path(__file__).resolve().parents[1] / "load" / "load.py"
SRC = LOAD_PY.read_text(encoding="utf-8")


def _func_src(name: str) -> str:
    start = SRC.index(f"def {name}(")
    nxt = SRC.find("\ndef ", start + 1)
    return SRC[start:] if nxt == -1 else SRC[start:nxt]


def test_resolve_src_raises_on_unknown_source():
    body = _func_src("resolve_src")
    assert "raise" in body, "resolve_src must fail-fast on unknown source_name"
    assert "return None" not in body, "resolve_src must not silently return None"


def test_no_import_batches_or_create_batch():
    assert "create_batch" not in SRC, "create_batch wiring must be removed"
    assert "import_batches" not in SRC, "import_batches must not be referenced by the loader"


def test_no_source_batch_id_inserts():
    assert "source_batch_id" not in SRC, "loader must not write source_batch_id"


def test_link_loaders_insert_source_url():
    pc = _func_src("load_plant_compounds")
    assert "source_url" in pc, "plant_compounds insert must include source_url"
    dt = _func_src("load_disease_targets")
    assert "source_url" in dt, "disease_targets insert must include source_url"


def test_entity_loaders_keep_source_url_and_source_id():
    for fn in ("load_plants", "load_compounds", "load_diseases", "load_targets"):
        body = _func_src(fn)
        assert "source_url" in body
        assert "resolve_src" in body  # per-row source_id retained
