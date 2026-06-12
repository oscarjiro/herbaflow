"""AnalysisCreate input-mode validation matrix (entry-modes §6)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisCreate

PID = str(uuid.uuid4())
DID = str(uuid.uuid4())
TID = str(uuid.uuid4())
CID = str(uuid.uuid4())


def test_selection_defaults_ok() -> None:
    m = AnalysisCreate(plant_ids=[PID], disease_id=DID)
    assert m.plant_input_mode.value == "selection"
    assert m.disease_input_mode.value == "selection"


def test_selection_requires_plant_and_disease() -> None:
    with pytest.raises(ValidationError):
        AnalysisCreate(plant_ids=[], disease_id=DID)  # no plant
    with pytest.raises(ValidationError):
        AnalysisCreate(plant_ids=[PID])  # no disease


def test_manual_compounds_forbids_plants_requires_compounds() -> None:
    ok = AnalysisCreate(
        plant_input_mode="manual_compounds", manual_compound_ids=[CID], disease_id=DID
    )
    assert ok.plant_label is None
    with pytest.raises(ValidationError):  # plants forbidden in manual_compounds
        AnalysisCreate(
            plant_input_mode="manual_compounds",
            plant_ids=[PID],
            manual_compound_ids=[CID],
            disease_id=DID,
        )
    with pytest.raises(ValidationError):  # compounds required
        AnalysisCreate(plant_input_mode="manual_compounds", disease_id=DID)


def test_manual_targets_forbids_plants_and_compounds() -> None:
    AnalysisCreate(plant_input_mode="manual_targets", manual_target_ids=[TID], disease_id=DID)
    with pytest.raises(ValidationError):
        AnalysisCreate(
            plant_input_mode="manual_targets",
            manual_compound_ids=[CID],
            manual_target_ids=[TID],
            disease_id=DID,
        )


def test_manual_disease_forbids_disease_id_requires_targets() -> None:
    AnalysisCreate(
        plant_ids=[PID],
        disease_input_mode="manual_disease_targets",
        manual_disease_target_ids=[TID],
    )
    with pytest.raises(ValidationError):
        AnalysisCreate(
            plant_ids=[PID],
            disease_input_mode="manual_disease_targets",
            disease_id=DID,
            manual_disease_target_ids=[TID],
        )
    with pytest.raises(ValidationError):
        AnalysisCreate(plant_ids=[PID], disease_input_mode="manual_disease_targets")


def test_label_rejected_on_selection_mode() -> None:
    with pytest.raises(ValidationError):
        AnalysisCreate(plant_ids=[PID], disease_id=DID, plant_label="custom")
    # label allowed on a manual mode
    AnalysisCreate(
        plant_input_mode="manual_targets",
        manual_target_ids=[TID],
        disease_id=DID,
        plant_label="custom extract",
    )
