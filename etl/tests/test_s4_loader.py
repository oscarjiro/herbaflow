from pathlib import Path

LOAD_PY = Path(__file__).resolve().parents[1] / "load" / "load.py"
SRC = LOAD_PY.read_text(encoding="utf-8")


def _func_src(name: str) -> str:
    start = SRC.index(f"def {name}(")
    nxt = SRC.find("\ndef ", start + 1)
    return SRC[start:] if nxt == -1 else SRC[start:nxt]


def test_loader_drops_dead_columns():
    for fn in ("load_plants", "load_compounds", "load_plant_compounds",
               "load_diseases", "load_targets", "load_disease_targets"):
        assert "confidence" not in _func_src(fn), f"{fn} still inserts confidence"
    pc = _func_src("load_plant_compounds")
    assert "evidence_type" not in pc
    assert "source_plant_raw_id" not in pc
    assert "source_compound_raw_id" not in pc
    # kept columns survive in their loaders
    assert "cas_id" in _func_src("load_compounds")
    assert "gbif_usage_key" in _func_src("load_plants")
    dt = _func_src("load_disease_targets")
    assert "association_type" in dt
    assert "score" in dt
