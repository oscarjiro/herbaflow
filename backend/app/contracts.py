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


def max_compounds() -> int:
    """Maximum compounds in one run (shared input bound, RS.2)."""
    return int(_defs()["limits"]["properties"]["max_compounds"]["const"])


def max_targets() -> int:
    """Maximum targets in one run (shared input bound, RS.2)."""
    return int(_defs()["limits"]["properties"]["max_targets"]["const"])


@lru_cache(maxsize=1)
def default_mode() -> str:
    return cast(str, _defs()["mode"]["default"])


def adme_defaults() -> dict[str, Any]:
    """The frozen-at-create defaults for the adme param group (from the contract)."""
    props = pipeline_parameters()["adme"]["properties"]
    return {name: spec["default"] for name, spec in props.items()}


def pipeline_param_bounds(group: str) -> dict[str, Any]:
    """The JSON-Schema property map for a param group (used for override-bounds validation)."""
    return cast(dict[str, Any], pipeline_parameters()[group]["properties"])


def adme_param_meta() -> dict[str, Any]:
    """Per-param UI metadata: default + hard bounds + advisory recommended range + description.

    The contract is the single lock-cited source. ``min``/``max`` are the HARD validation bounds
    (``exclusiveMinimum`` is surfaced as ``min`` too); ``recommended_*`` are the advisory lock
    range.
    """
    out: dict[str, Any] = {}
    for name, spec in pipeline_parameters()["adme"]["properties"].items():
        out[name] = {
            "default": spec.get("default"),
            "min": spec.get("minimum", spec.get("exclusiveMinimum")),
            "max": spec.get("maximum"),
            "recommended_min": spec.get("recommended_min"),
            "recommended_max": spec.get("recommended_max"),
            "description": spec.get("description"),
        }
    return out


def target_defaults() -> dict[str, Any]:
    """The frozen-at-create defaults for the target param group (from the contract)."""
    props = pipeline_parameters()["target"]["properties"]
    return {name: spec["default"] for name, spec in props.items()}


def target_param_meta() -> dict[str, Any]:
    """Per-param UI metadata for the target group (bounds, advisory range, description)."""
    out: dict[str, Any] = {}
    for name, spec in pipeline_parameters()["target"]["properties"].items():
        out[name] = {
            "default": spec.get("default"),
            "min": spec.get("minimum", spec.get("exclusiveMinimum")),
            "max": spec.get("maximum"),
            "recommended_min": spec.get("recommended_min"),
            "recommended_max": spec.get("recommended_max"),
            "description": spec.get("description"),
        }
    return out
