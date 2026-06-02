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
