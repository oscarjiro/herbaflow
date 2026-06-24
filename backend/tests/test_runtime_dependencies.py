from __future__ import annotations

import tomllib
from pathlib import Path


def test_httpx_is_a_runtime_dependency() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert any(dependency.split(">=", 1)[0] == "httpx" for dependency in dependencies)
