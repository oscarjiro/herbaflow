"""Pure mode -> per-stage-state matrix for the entry-modes chunk (EM-4/EM-5).

Plant mode governs stages 1-3 + the plant entity; disease mode governs stage 4 + the disease
entity; stages 5-8 are always ``computed``. ``frozen_stages`` are the stages the engine must NOT
compute (it skips ``user_provided`` pre-filled stages and ``not_applicable`` stages on run AND
reset-from). The frozen set is derived from the chosen modes, never from the presentational
``stage_results[n].state`` (which also reads ``user_provided`` for edited computed stages --
Software Lock §2.3/§5.7).
"""

from __future__ import annotations

from typing import Any

COMPUTED = "computed"
USER_PROVIDED = "user_provided"
NOT_APPLICABLE = "not_applicable"

_PLANT_MODES = ("selection", "manual_compounds", "manual_targets")
_DISEASE_MODES = ("selection", "manual_disease_targets")

# Plant mode -> states for (S1, S2, S3). D4: manual_compounds keeps S2 computed (ADME runs).
_PLANT_STATES: dict[str, tuple[str, str, str]] = {
    "selection": (COMPUTED, COMPUTED, COMPUTED),
    "manual_compounds": (USER_PROVIDED, COMPUTED, COMPUTED),
    "manual_targets": (NOT_APPLICABLE, NOT_APPLICABLE, USER_PROVIDED),
}
# Disease mode -> state for S4.
# D5: manual_disease_targets -> S4 user_provided (entity N/A elsewhere).
_DISEASE_S4: dict[str, str] = {
    "selection": COMPUTED,
    "manual_disease_targets": USER_PROVIDED,
}


def stage_state_map(plant_mode: str, disease_mode: str) -> dict[int, str]:
    """The full {stage -> state} map (stages 1-8) for the chosen modes."""
    if plant_mode not in _PLANT_MODES:
        raise ValueError(f"unknown plant_input_mode: {plant_mode}")
    if disease_mode not in _DISEASE_MODES:
        raise ValueError(f"unknown disease_input_mode: {disease_mode}")
    s1, s2, s3 = _PLANT_STATES[plant_mode]
    return {
        1: s1,
        2: s2,
        3: s3,
        4: _DISEASE_S4[disease_mode],
        5: COMPUTED,
        6: COMPUTED,
        7: COMPUTED,
        8: COMPUTED,
    }


def frozen_stages(plant_mode: str, disease_mode: str) -> frozenset[int]:
    """Stages the engine must NOT compute (user_provided pre-filled OR not_applicable)."""
    smap = stage_state_map(plant_mode, disease_mode)
    return frozenset(s for s, st in smap.items() if st in (USER_PROVIDED, NOT_APPLICABLE))


def first_computed_stage(plant_mode: str, disease_mode: str) -> int:
    """The run cursor: the smallest stage whose state is ``computed``."""
    smap = stage_state_map(plant_mode, disease_mode)
    return min(s for s, st in smap.items() if st == COMPUTED)


def modes_from_params(parameters: dict[str, Any]) -> tuple[str, str]:
    """Read (plant_mode, disease_mode) from a run's parameters, defaulting to selection."""
    im = parameters.get("input_modes") or {}
    return im.get("plant", "selection"), im.get("disease", "selection")


def frozen_stages_from_params(parameters: dict[str, Any]) -> frozenset[int]:
    """Frozen set for a stored run (empty for pre-entry-modes runs with no input_modes)."""
    plant, disease = modes_from_params(parameters)
    return frozen_stages(plant, disease)


# Plant modes that introduce compounds (Stage 1/3 compound path). manual_targets supplies
# resolved targets directly and has NO compounds, so compound-only outputs (CTP network)
# are not applicable to it.
_COMPOUND_PLANT_MODES = ("selection", "manual_compounds")


def has_compounds(plant_mode: str) -> bool:
    """True when the plant side introduces compounds (selection or manual_compounds)."""
    return plant_mode in _COMPOUND_PLANT_MODES


def has_compounds_from_params(parameters: dict[str, Any]) -> bool:
    """True when a stored run has compounds (defaults to True for pre-entry-modes runs)."""
    plant, _ = modes_from_params(parameters)
    return has_compounds(plant)
