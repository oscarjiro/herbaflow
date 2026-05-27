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

    def test_non_preset_one_rejected(self):
        """1.0 is not a STRING-DB preset — must be rejected."""
        with pytest.raises(ValidationError, match="min_confidence"):
            CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 1.0}}))


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


# ---------------------------------------------------------------------------
# ppi.min_confidence — STRING confidence presets: 0.15, 0.40, 0.70, 0.90
# ---------------------------------------------------------------------------

class TestStringConfidencePresets:
    def test_non_preset_value_rejected(self):
        """ppi.min_confidence must be one of the 4 STRING-DB preset values."""
        with pytest.raises(ValidationError, match="min_confidence"):
            CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.55}}))

    def test_another_non_preset_rejected(self):
        with pytest.raises(ValidationError, match="min_confidence"):
            CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.30}}))

    def test_low_preset_accepted(self):
        req = CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.15}}))
        assert req.parameters["ppi"]["min_confidence"] == pytest.approx(0.15)

    def test_medium_preset_accepted(self):
        req = CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.40}}))
        assert req.parameters["ppi"]["min_confidence"] == pytest.approx(0.40)

    def test_high_preset_accepted(self):
        req = CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.70}}))
        assert req.parameters["ppi"]["min_confidence"] == pytest.approx(0.70)

    def test_very_high_preset_accepted(self):
        req = CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.90}}))
        assert req.parameters["ppi"]["min_confidence"] == pytest.approx(0.90)

    def test_reset_request_enforces_presets(self):
        with pytest.raises(ValidationError, match="min_confidence"):
            _reset({"ppi": {"min_confidence": 0.55}})

    def test_approve_request_enforces_presets(self):
        with pytest.raises(ValidationError, match="min_confidence"):
            _approve({"ppi": {"min_confidence": 0.55}})


# ---------------------------------------------------------------------------
# Error message humanization — app/errors.py constants
# ---------------------------------------------------------------------------

# Python exception class names that must NEVER appear in an API detail field.
_FORBIDDEN_EXCEPTION_NAMES = {
    "TypeError",
    "ValueError",
    "AttributeError",
    "KeyError",
    "IndexError",
    "RuntimeError",
    "Exception",
    "HTTPError",
    "HTTPStatusError",
    "ConnectionError",
    "TimeoutError",
}


class TestErrorConstants:
    """Verify that app/errors.py constants are non-empty human-readable strings
    that do not leak Python exception class names."""

    def _load_constants(self) -> dict:
        from app.errors import (
            PUBCHEM_UNAVAILABLE,
            PUBCHEM_VALIDATION_FAILED,
            UNIPROT_UNAVAILABLE,
            UNIPROT_TARGET_NOT_FOUND,
            UNIPROT_VALIDATION_FAILED,
            CHEMBL_UNAVAILABLE,
            STRING_UNAVAILABLE,
            ANALYSIS_NOT_FOUND,
            COMPOUND_NOT_FOUND,
            TARGET_NOT_FOUND,
            STAGE_NOT_READY,
            INVALID_STAGE,
            TARGET_ALREADY_EXISTS,
        )
        return {
            "PUBCHEM_UNAVAILABLE": PUBCHEM_UNAVAILABLE,
            "PUBCHEM_VALIDATION_FAILED": PUBCHEM_VALIDATION_FAILED,
            "UNIPROT_UNAVAILABLE": UNIPROT_UNAVAILABLE,
            "UNIPROT_TARGET_NOT_FOUND": UNIPROT_TARGET_NOT_FOUND,
            "UNIPROT_VALIDATION_FAILED": UNIPROT_VALIDATION_FAILED,
            "CHEMBL_UNAVAILABLE": CHEMBL_UNAVAILABLE,
            "STRING_UNAVAILABLE": STRING_UNAVAILABLE,
            "ANALYSIS_NOT_FOUND": ANALYSIS_NOT_FOUND,
            "COMPOUND_NOT_FOUND": COMPOUND_NOT_FOUND,
            "TARGET_NOT_FOUND": TARGET_NOT_FOUND,
            "STAGE_NOT_READY": STAGE_NOT_READY,
            "INVALID_STAGE": INVALID_STAGE,
            "TARGET_ALREADY_EXISTS": TARGET_ALREADY_EXISTS,
        }

    def test_all_constants_are_non_empty_strings(self):
        """Every constant must be a non-empty string."""
        constants = self._load_constants()
        for name, value in constants.items():
            assert isinstance(value, str), f"{name} must be a str"
            assert value.strip(), f"{name} must not be empty or whitespace"

    def test_no_constant_contains_exception_class_name(self):
        """No constant may contain a bare Python exception class name."""
        constants = self._load_constants()
        for const_name, value in constants.items():
            for exc_name in _FORBIDDEN_EXCEPTION_NAMES:
                assert exc_name not in value, (
                    f"{const_name} leaks exception class name '{exc_name}': {value!r}"
                )

    def test_service_unavailable_messages_are_actionable(self):
        """Service-unavailable messages must tell the user to retry."""
        from app.errors import (
            PUBCHEM_UNAVAILABLE,
            UNIPROT_UNAVAILABLE,
            CHEMBL_UNAVAILABLE,
            STRING_UNAVAILABLE,
        )
        for msg in [PUBCHEM_UNAVAILABLE, UNIPROT_UNAVAILABLE, CHEMBL_UNAVAILABLE, STRING_UNAVAILABLE]:
            assert any(
                kw in msg.lower() for kw in ("try again", "unavailable", "retry")
            ), f"Service-unavailable message should be actionable: {msg!r}"

    def test_not_found_messages_are_concise(self):
        """Not-found messages must be short user-readable strings, not stack frames."""
        from app.errors import ANALYSIS_NOT_FOUND, COMPOUND_NOT_FOUND, TARGET_NOT_FOUND
        for msg in [ANALYSIS_NOT_FOUND, COMPOUND_NOT_FOUND, TARGET_NOT_FOUND]:
            assert len(msg) < 120, f"Not-found message is unexpectedly long: {msg!r}"
            assert "Traceback" not in msg
            assert "File " not in msg


class TestRouterErrorsNoRawExceptionStrings:
    """Whitebox: verify that the analyses router module does not expose raw
    exception text directly in HTTPException detail fields.

    This complements the constant tests above by checking the source code
    at import time (no network calls needed).
    """

    def test_analyses_router_has_no_str_exc_in_http_exception_detail(self):
        """The analyses router must not pass str(exc) directly as an HTTPException detail.

        We check by inspecting the source code of the router module — the pattern
        'detail=str(e' or 'detail=str(exc' must not appear.
        """
        import inspect
        import app.routers.analyses as analyses_module

        source = inspect.getsource(analyses_module)
        # These patterns would leak raw exception text into HTTP responses.
        forbidden_patterns = [
            "detail=str(e)",
            "detail=str(exc)",
            'detail=f"PubChem validation failed: {str(e)}',
            'detail=f"PubChem validation failed: {str(exc)}',
        ]
        for pattern in forbidden_patterns:
            assert pattern not in source, (
                f"Raw exception string found in analyses router detail: {pattern!r}"
            )
