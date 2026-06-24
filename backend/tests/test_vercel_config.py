from __future__ import annotations

import json
from pathlib import Path

from app import contracts


def test_backend_service_uses_packaged_contract_not_external_include() -> None:
    config = json.loads((Path(__file__).parents[2] / "vercel.json").read_text(encoding="utf-8"))

    backend = config["experimentalServices"]["backend"]

    assert "includeFiles" not in backend


def test_packaged_contract_matches_shared_contract() -> None:
    backend_root = Path(__file__).parents[1]
    repo_root = Path(__file__).parents[2]

    packaged = backend_root / "app" / "generated" / "analysis_contract.json"
    shared = repo_root / "shared" / "contracts" / "analysis.json"

    assert json.loads(packaged.read_text(encoding="utf-8")) == json.loads(
        shared.read_text(encoding="utf-8")
    )


def test_contract_path_resolves_from_vercel_backend_bundle_layout(tmp_path: Path) -> None:
    bundle_root = tmp_path / "task"
    app_file = bundle_root / "app" / "contracts.py"
    contract = bundle_root / "shared" / "contracts" / "analysis.json"
    app_file.parent.mkdir(parents=True)
    contract.parent.mkdir(parents=True)
    contract.write_text("{}", encoding="utf-8")

    assert contracts._resolve_contract_path(app_file) == contract


def test_contract_path_resolves_packaged_contract_when_shared_contract_is_not_bundled(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "task"
    app_file = bundle_root / "app" / "contracts.py"
    contract = bundle_root / "app" / "generated" / "analysis_contract.json"
    app_file.parent.mkdir(parents=True)
    contract.parent.mkdir(parents=True)
    contract.write_text("{}", encoding="utf-8")

    assert contracts._resolve_contract_path(app_file) == contract
