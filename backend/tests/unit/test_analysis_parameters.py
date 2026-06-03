# backend/tests/unit/test_analysis_parameters.py
import pytest
from pydantic import ValidationError
from app.schemas.analysis import AnalysisParameters


def test_valid_nested_accepted():
    p = AnalysisParameters.model_validate(
        {"adme": {"max_mw": 600}, "target": {"min_pchembl": 6.0}}
    )
    assert p.adme.max_mw == 600
    assert p.target.min_pchembl == 6.0
    assert p.model_dump(exclude_none=True) == {
        "adme": {"max_mw": 600}, "target": {"min_pchembl": 6.0},
    }


def test_flat_payload_rejected():
    # Flat top-level keys are unknown at the top level -> extra=forbid -> 422
    with pytest.raises(ValidationError):
        AnalysisParameters.model_validate({"max_mw": 600, "min_pchembl": 6.0})


def test_unknown_key_rejected():
    with pytest.raises(ValidationError):
        AnalysisParameters.model_validate({"adme": {"bogus": 1}})


def test_out_of_range_rejected():
    with pytest.raises(ValidationError):
        AnalysisParameters.model_validate({"target": {"min_pchembl": 99}})
    with pytest.raises(ValidationError):
        AnalysisParameters.model_validate({"adme": {"max_mw": 0}})


def test_ppi_confidence_preset_enforced():
    with pytest.raises(ValidationError):
        AnalysisParameters.model_validate({"ppi": {"min_confidence": 0.5}})
    ok = AnalysisParameters.model_validate({"ppi": {"min_confidence": 0.4}})
    assert ok.ppi.min_confidence == 0.4


def test_empty_is_valid_and_dumps_empty():
    assert AnalysisParameters().model_dump(exclude_none=True) == {}
