"""Pure mode -> stage-state matrix (entry-modes EM-4/EM-5)."""

from __future__ import annotations

import pytest

from app.pipeline import entry_modes as em

# (plant_mode, disease_mode) -> (stage_state_map, frozen_stages, first_computed_stage)
CASES = [
    (
        ("selection", "selection"),
        {
            1: "computed",
            2: "computed",
            3: "computed",
            4: "computed",
            5: "computed",
            6: "computed",
            7: "computed",
            8: "computed",
        },
        frozenset(),
        1,
    ),
    (
        ("manual_compounds", "selection"),
        {
            1: "user_provided",
            2: "computed",
            3: "computed",
            4: "computed",
            5: "computed",
            6: "computed",
            7: "computed",
            8: "computed",
        },
        frozenset({1}),
        2,
    ),
    (
        ("manual_targets", "selection"),
        {
            1: "not_applicable",
            2: "not_applicable",
            3: "user_provided",
            4: "computed",
            5: "computed",
            6: "computed",
            7: "computed",
            8: "computed",
        },
        frozenset({1, 2, 3}),
        4,
    ),
    (
        ("selection", "manual_disease_targets"),
        {
            1: "computed",
            2: "computed",
            3: "computed",
            4: "user_provided",
            5: "computed",
            6: "computed",
            7: "computed",
            8: "computed",
        },
        frozenset({4}),
        1,
    ),
    (
        ("manual_targets", "manual_disease_targets"),
        {
            1: "not_applicable",
            2: "not_applicable",
            3: "user_provided",
            4: "user_provided",
            5: "computed",
            6: "computed",
            7: "computed",
            8: "computed",
        },
        frozenset({1, 2, 3, 4}),
        5,
    ),
    (
        ("manual_compounds", "manual_disease_targets"),
        {
            1: "user_provided",
            2: "computed",
            3: "computed",
            4: "user_provided",
            5: "computed",
            6: "computed",
            7: "computed",
            8: "computed",
        },
        frozenset({1, 4}),
        2,
    ),
]


@pytest.mark.parametrize("modes,smap,frozen,first", CASES)
def test_matrix(modes, smap, frozen, first) -> None:
    plant, disease = modes
    assert em.stage_state_map(plant, disease) == smap
    assert em.frozen_stages(plant, disease) == frozen
    assert em.first_computed_stage(plant, disease) == first


def test_missing_modes_default_to_selection() -> None:
    # A run created before entry-modes has no input_modes -> treat as all-selection.
    assert em.frozen_stages_from_params({}) == frozenset()
    assert em.frozen_stages_from_params(
        {"input_modes": {"plant": "manual_targets", "disease": "selection"}}
    ) == frozenset({1, 2, 3})
