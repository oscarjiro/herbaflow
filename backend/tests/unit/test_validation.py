"""Unit tests for Pydantic parameter bound validation on analysis request schemas.

Tests double-sided validation (T5.2): ensures critical numeric params are
rejected at the backend schema layer when they would cause runtime errors
(log(0), divide-by-zero, empty result sets) if passed to pipeline stages.

All tests are synchronous — pure Pydantic model instantiation, no DB or mocks.
"""
import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    ApproveRequest,
    CreateAnalysisRequest,
    ResetFromRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create(parameters: dict | None = None) -> dict:
    """Minimal valid CreateAnalysisRequest payload."""
    return {
        "name": "Test run",
        "disease_ids": ["disease-1"],
        "parameters": parameters or {},
    }


def _reset(params: dict | None = None) -> ResetFromRequest:
    return ResetFromRequest(params=params, rerun=False)


def _approve(param_overrides: dict | None = None) -> ApproveRequest:
    return ApproveRequest(param_overrides=param_overrides)


# ---------------------------------------------------------------------------
# enrichment.fdr_threshold — must be in (0, 1]
# ---------------------------------------------------------------------------

class TestFdrThreshold:
    def test_zero_rejected(self):
        """fdr_threshold=0 → log(0) in Stage 8 — must be rejected."""
        with pytest.raises(ValidationError, match="fdr_threshold"):
            CreateAnalysisRequest(**_create({"enrichment": {"fdr_threshold": 0}}))

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="fdr_threshold"):
            CreateAnalysisRequest(**_create({"enrichment": {"fdr_threshold": -0.1}}))

    def test_above_one_rejected(self):
        with pytest.raises(ValidationError, match="fdr_threshold"):
            CreateAnalysisRequest(**_create({"enrichment": {"fdr_threshold": 1.01}}))

    def test_valid_typical(self):
        req = CreateAnalysisRequest(**_create({"enrichment": {"fdr_threshold": 0.05}}))
        assert req.parameters["enrichment"]["fdr_threshold"] == 0.05

    def test_boundary_one_accepted(self):
        """Upper bound is inclusive — fdr_threshold=1 is valid."""
        req = CreateAnalysisRequest(**_create({"enrichment": {"fdr_threshold": 1.0}}))
        assert req.parameters["enrichment"]["fdr_threshold"] == 1.0

    def test_boundary_near_zero_accepted(self):
        req = CreateAnalysisRequest(**_create({"enrichment": {"fdr_threshold": 0.001}}))
        assert req.parameters["enrichment"]["fdr_threshold"] == pytest.approx(0.001)

    def test_reset_request_enforces_bound(self):
        with pytest.raises(ValidationError, match="fdr_threshold"):
            _reset({"enrichment": {"fdr_threshold": 0}})

    def test_approve_request_enforces_bound(self):
        with pytest.raises(ValidationError, match="fdr_threshold"):
            _approve({"enrichment": {"fdr_threshold": 0}})


# ---------------------------------------------------------------------------
# adme.max_mw — must be > 0
# ---------------------------------------------------------------------------

class TestAdmeMaxMw:
    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="max_mw"):
            CreateAnalysisRequest(**_create({"adme": {"max_mw": 0}}))

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="max_mw"):
            CreateAnalysisRequest(**_create({"adme": {"max_mw": -100}}))

    def test_valid(self):
        req = CreateAnalysisRequest(**_create({"adme": {"max_mw": 500}}))
        assert req.parameters["adme"]["max_mw"] == 500


# ---------------------------------------------------------------------------
# target.min_pchembl — must be in [0, 14]
# ---------------------------------------------------------------------------

class TestTargetMinPchembl:
    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="min_pchembl"):
            CreateAnalysisRequest(**_create({"target": {"min_pchembl": -1.0}}))

    def test_above_fourteen_rejected(self):
        with pytest.raises(ValidationError, match="min_pchembl"):
            CreateAnalysisRequest(**_create({"target": {"min_pchembl": 14.1}}))

    def test_zero_accepted(self):
        req = CreateAnalysisRequest(**_create({"target": {"min_pchembl": 0.0}}))
        assert req.parameters["target"]["min_pchembl"] == 0.0

    def test_fourteen_accepted(self):
        req = CreateAnalysisRequest(**_create({"target": {"min_pchembl": 14.0}}))
        assert req.parameters["target"]["min_pchembl"] == 14.0


# ---------------------------------------------------------------------------
# target.min_assay_confidence — must be in [0, 9]
# ---------------------------------------------------------------------------

class TestTargetMinAssayConfidence:
    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="min_assay_confidence"):
            CreateAnalysisRequest(**_create({"target": {"min_assay_confidence": -1}}))

    def test_above_nine_rejected(self):
        with pytest.raises(ValidationError, match="min_assay_confidence"):
            CreateAnalysisRequest(**_create({"target": {"min_assay_confidence": 10}}))

    def test_zero_accepted(self):
        req = CreateAnalysisRequest(**_create({"target": {"min_assay_confidence": 0}}))
        assert req.parameters["target"]["min_assay_confidence"] == 0

    def test_nine_accepted(self):
        req = CreateAnalysisRequest(**_create({"target": {"min_assay_confidence": 9}}))
        assert req.parameters["target"]["min_assay_confidence"] == 9


# ---------------------------------------------------------------------------
# hub_genes.top_n — must be >= 1
# ---------------------------------------------------------------------------

class TestHubGenesTopN:
    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="top_n"):
            CreateAnalysisRequest(**_create({"hub_genes": {"top_n": 0}}))

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="top_n"):
            CreateAnalysisRequest(**_create({"hub_genes": {"top_n": -5}}))

    def test_one_accepted(self):
        req = CreateAnalysisRequest(**_create({"hub_genes": {"top_n": 1}}))
        assert req.parameters["hub_genes"]["top_n"] == 1


# ---------------------------------------------------------------------------
# ppi.min_confidence — must be in (0, 1]
# ---------------------------------------------------------------------------

class TestPpiMinConfidence:
    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="min_confidence"):
            CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0}}))

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="min_confidence"):
            CreateAnalysisRequest(**_create({"ppi": {"min_confidence": -0.1}}))

    def test_above_one_rejected(self):
        with pytest.raises(ValidationError, match="min_confidence"):
            CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 1.01}}))

    def test_typical_valid(self):
        req = CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.4}}))
        assert req.parameters["ppi"]["min_confidence"] == pytest.approx(0.4)

    def test_one_accepted(self):
        req = CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 1.0}}))
        assert req.parameters["ppi"]["min_confidence"] == 1.0


# ---------------------------------------------------------------------------
# Empty / absent sections — must pass (params are optional per-section)
# ---------------------------------------------------------------------------

class TestAbsentSections:
    def test_empty_parameters_ok(self):
        req = CreateAnalysisRequest(**_create({}))
        assert req.parameters == {}

    def test_unrelated_keys_pass_through(self):
        req = CreateAnalysisRequest(**_create({"_input_mode": "manual_compounds"}))
        assert req.parameters["_input_mode"] == "manual_compounds"

    def test_reset_none_params_ok(self):
        req = _reset(None)
        assert req.params is None

    def test_approve_none_overrides_ok(self):
        req = _approve(None)
        assert req.param_overrides is None
