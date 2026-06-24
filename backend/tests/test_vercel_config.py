from __future__ import annotations

import json
from pathlib import Path

from app import contracts


def test_backend_service_includes_shared_contract() -> None:
    config = json.loads((Path(__file__).parents[2] / "vercel.json").read_text(encoding="utf-8"))

    backend = config["experimentalServices"]["backend"]

    assert "../../shared/contracts/analysis.json" in backend["includeFiles"]


def test_contract_path_resolves_from_vercel_backend_bundle_layout(tmp_path: Path) -> None:
    bundle_root = tmp_path / "task"
    app_file = bundle_root / "app" / "contracts.py"
    contract = bundle_root / "shared" / "contracts" / "analysis.json"
    app_file.parent.mkdir(parents=True)
    contract.parent.mkdir(parents=True)
    contract.write_text("{}", encoding="utf-8")

    assert contracts._resolve_contract_path(app_file) == contract
