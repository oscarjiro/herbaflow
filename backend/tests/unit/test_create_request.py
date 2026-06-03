# backend/tests/unit/test_create_request.py
import pytest
from pydantic import ValidationError
from app.schemas.analysis import CreateAnalysisRequest


def _base(**kw):
    data = {"name": "x", "mode": "guided", "plant_ids": ["p1"], "disease_id": "d1"}
    data.update(kw)
    return data


def test_nested_params_accepted():
    req = CreateAnalysisRequest.model_validate(_base(parameters={"adme": {"max_mw": 600}}))
    assert req.parameters.adme.max_mw == 600


def test_flat_params_rejected():
    with pytest.raises(ValidationError):
        CreateAnalysisRequest.model_validate(_base(parameters={"max_mw": 600}))


def test_manual_compounds_lifts_disease_requirement_off_manual_targets():
    # manual_disease_targets present -> disease_id may be null
    req = CreateAnalysisRequest.model_validate(
        _base(plant_ids=[], disease_id=None,
              compounds=["CCO"], manual_disease_targets=["TP53"])
    )
    assert req.compounds == ["CCO"]
    assert req.manual_disease_targets == ["TP53"]


def test_disease_required_when_no_manual_disease_targets():
    with pytest.raises(ValidationError):
        CreateAnalysisRequest.model_validate(_base(disease_id=None))


def test_compounds_and_targets_mutually_exclusive():
    with pytest.raises(ValidationError):
        CreateAnalysisRequest.model_validate(_base(compounds=["CCO"], targets=["TP53"]))
