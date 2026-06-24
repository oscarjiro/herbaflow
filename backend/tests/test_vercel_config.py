from __future__ import annotations

import json
from pathlib import Path


def test_backend_service_includes_shared_contract() -> None:
    config = json.loads((Path(__file__).parents[2] / "vercel.json").read_text(encoding="utf-8"))

    backend = config["experimentalServices"]["backend"]

    assert "shared/contracts/analysis.json" in backend["includeFiles"]
