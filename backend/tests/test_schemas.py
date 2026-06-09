import uuid

import pytest
from pydantic import ValidationError

from app import contracts
from app.schemas.analysis import AnalysisCreate, Mode


def test_mode_matches_contract() -> None:
    assert {m.value for m in Mode} == set(contracts.modes())


def test_plant_cap_enforced() -> None:
    too_many = [uuid.uuid4() for _ in range(contracts.max_plants() + 1)]
    with pytest.raises(ValidationError):
        AnalysisCreate(plant_ids=too_many, disease_id=uuid.uuid4())


def test_requires_at_least_one_plant() -> None:
    with pytest.raises(ValidationError):
        AnalysisCreate(plant_ids=[], disease_id=uuid.uuid4())


def test_defaults_to_contract_mode() -> None:
    payload = AnalysisCreate(plant_ids=[uuid.uuid4()], disease_id=uuid.uuid4())
    assert payload.mode == Mode.guided
    assert payload.mode.value == contracts.default_mode()
