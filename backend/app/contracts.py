"""Loader for the shared cross-stack contract (/shared/contracts/analysis.json).

The contract is the single upstream source for analysis-domain vocabularies and
pipeline-parameter bounds. Both stacks read it; this module is the backend read side.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "shared" / "contracts" / "analysis.json"


@lru_cache(maxsize=1)
def raw() -> dict[str, Any]:
    """Parse and cache the contract document."""
    return cast(dict[str, Any], json.loads(_CONTRACT_PATH.read_text(encoding="utf-8")))


def _defs() -> dict[str, Any]:
    return cast(dict[str, Any], raw()["$defs"])


def modes() -> tuple[str, ...]:
    return tuple(_defs()["mode"]["enum"])


def stage_states() -> tuple[str, ...]:
    return tuple(_defs()["stage_state"]["enum"])


def run_status_flat() -> tuple[str, ...]:
    return tuple(_defs()["run_status_flat"]["enum"])


def stage_phases() -> tuple[str, ...]:
    return tuple(_defs()["stage_phase"]["enum"])


def pipeline_parameters() -> dict[str, Any]:
    """The pipeline_parameters property map (group -> JSON-Schema object)."""
    return cast(dict[str, Any], _defs()["pipeline_parameters"]["properties"])


def max_plants() -> int:
    """Maximum plants selectable for one run (shared input bound)."""
    return int(_defs()["limits"]["properties"]["max_plants"]["const"])


@lru_cache(maxsize=1)
def default_mode() -> str:
    value = _defs()["mode"]["default"]
    assert isinstance(value, str)
    return value
