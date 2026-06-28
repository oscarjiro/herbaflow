"""Loader for the shared cross-stack contract (/shared/contracts/analysis.json).

The contract is the single upstream source for analysis-domain vocabularies and
pipeline-parameter bounds. Both stacks read it; this module is the backend read side.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast


def _resolve_contract_path(module_path: Path) -> Path:
    resolved_module = module_path.resolve()
    for parent in resolved_module.parents:
        candidate = parent / "shared" / "contracts" / "analysis.json"
        if candidate.exists():
            return candidate
    packaged = resolved_module.parent / "generated" / "analysis_contract.json"
    if packaged.exists():
        return packaged
    return resolved_module.parents[2] / "shared" / "contracts" / "analysis.json"


_CONTRACT_PATH = _resolve_contract_path(Path(__file__))


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


def plant_input_modes() -> tuple[str, ...]:
    return tuple(_defs()["plant_input_mode"]["enum"])


def disease_input_modes() -> tuple[str, ...]:
    return tuple(_defs()["disease_input_mode"]["enum"])


@lru_cache(maxsize=1)
def default_plant_input_mode() -> str:
    return cast(str, _defs()["plant_input_mode"]["default"])


@lru_cache(maxsize=1)
def default_disease_input_mode() -> str:
    return cast(str, _defs()["disease_input_mode"]["default"])


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
    """The JSON-Schema property map for a param group (param_key -> {description, unit?, ...}).

    The single generic accessor over ``pipeline_parameters[group].properties`` — backs both
    override-bounds validation (``pipeline.engine.validate_overrides``) and report param metadata
    (``pipeline.report``). Each property carries the raw contract keys: ``default``, ``minimum``/
    ``exclusiveMinimum``/``maximum`` (hard bounds), the advisory ``recommended_min``/
    ``recommended_max``, ``enum``, ``unit``, and ``description``.
    """
    return cast(dict[str, Any], pipeline_parameters()[group]["properties"])


def target_defaults() -> dict[str, Any]:
    """The frozen-at-create defaults for the target param group (from the contract)."""
    props = pipeline_parameters()["target"]["properties"]
    return {name: spec["default"] for name, spec in props.items()}


def disease_targets_defaults() -> dict[str, Any]:
    """The frozen-at-create defaults for the disease_targets param group (from the contract)."""
    props = pipeline_parameters()["disease_targets"]["properties"]
    return {name: spec["default"] for name, spec in props.items()}


def ppi_defaults() -> dict[str, Any]:
    """The frozen-at-create defaults for the ppi param group (from the contract)."""
    props = pipeline_parameters()["ppi"]["properties"]
    return {name: spec["default"] for name, spec in props.items()}


def hub_genes_defaults() -> dict[str, Any]:
    """The frozen-at-create defaults for the hub_genes param group (from the contract)."""
    props = pipeline_parameters()["hub_genes"]["properties"]
    return {name: spec["default"] for name, spec in props.items()}


def enrichment_defaults() -> dict[str, Any]:
    """The frozen-at-create defaults for the enrichment param group (from the contract)."""
    props = pipeline_parameters()["enrichment"]["properties"]
    return {name: spec["default"] for name, spec in props.items()}


@lru_cache(maxsize=1)
def pipeline_stages() -> tuple[int, ...]:
    """Stage numbers present in the pipeline, derived from the contract stage_sources.

    Returns a sorted tuple of ints (e.g. (1, 2, 3, 4, 5, 6, 7, 8)).  Using the contract
    as the single source keeps this in sync with the stage_sources vocabulary without
    hardcoding the range in application code.
    """
    computed = _defs()["stage_sources"]["properties"]["computed"]["properties"]
    return tuple(sorted(int(k) for k in computed))


def stage_sources(stage: int, *, user_provided: bool = False) -> list[dict[str, str | None]]:
    """Per-stage data-source objects (contract-driven; one shared home with the FE).

    Each entry is ``{"name": str, "url": str | None}`` where ``url`` is ``None`` for
    pseudo-sources that have no canonical public page (e.g. set-intersection descriptions).

    ``user_provided`` returns only the manual-resolution source that actually runs for a
    user-supplied entity stage (S1/S3/S4); falls back to the computed list when no manual
    override is defined for that stage.
    """
    block = _defs()["stage_sources"]["properties"]
    key = str(stage)
    if user_provided:
        up = block["user_provided"]["properties"].get(key)
        if up is not None:
            return list(up["default"])
    comp = block["computed"]["properties"].get(key)
    return list(comp["default"]) if comp is not None else []
