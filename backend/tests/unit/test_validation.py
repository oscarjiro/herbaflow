"""Unit tests for Pydantic parameter bound validation on analysis request schemas.

Tests double-sided validation (T5.2): ensures critical numeric params are
rejected at the backend schema layer when they would cause runtime errors
(log(0), divide-by-zero, empty result sets) if passed to pipeline stages.

All tests are synchronous — pure Pydantic model instantiation, no DB or mocks.
"""
import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    AnalysisParameters,
    ApproveRequest,
    CreateAnalysisRequest,
    InjectCompoundsRequest,
    InjectTargetsRequest,
    ResetFromRequest,
    HARD_CAP_PLANTS,
    HARD_CAP_MANUAL_COMPOUNDS,
    HARD_CAP_MANUAL_TARGETS,
    HARD_CAP_DISEASE_TARGETS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create(parameters: dict | None = None) -> dict:
    """Minimal valid CreateAnalysisRequest payload."""
    return {
        "name": "Test run",
        "disease_id": "disease-1",
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
        assert req.parameters.enrichment.fdr_threshold == 0.05

    def test_boundary_one_accepted(self):
        """Upper bound is inclusive — fdr_threshold=1 is valid."""
        req = CreateAnalysisRequest(**_create({"enrichment": {"fdr_threshold": 1.0}}))
        assert req.parameters.enrichment.fdr_threshold == 1.0

    def test_boundary_near_zero_accepted(self):
        req = CreateAnalysisRequest(**_create({"enrichment": {"fdr_threshold": 0.001}}))
        assert req.parameters.enrichment.fdr_threshold == pytest.approx(0.001)

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
        assert req.parameters.adme.max_mw == 500


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
        assert req.parameters.target.min_pchembl == 0.0

    def test_fourteen_accepted(self):
        req = CreateAnalysisRequest(**_create({"target": {"min_pchembl": 14.0}}))
        assert req.parameters.target.min_pchembl == 14.0


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
        assert req.parameters.target.min_assay_confidence == 0

    def test_nine_accepted(self):
        req = CreateAnalysisRequest(**_create({"target": {"min_assay_confidence": 9}}))
        assert req.parameters.target.min_assay_confidence == 9


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
        assert req.parameters.hub_genes.top_n == 1


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
        assert req.parameters.ppi.min_confidence == pytest.approx(0.4)

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
        assert req.parameters == AnalysisParameters()

    def test_unrelated_keys_rejected(self):
        """Unknown / flat parameter keys are forbidden by the strict nested model."""
        with pytest.raises(ValidationError):
            CreateAnalysisRequest(**_create({"_input_mode": "manual_compounds"}))

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
        assert req.parameters.ppi.min_confidence == pytest.approx(0.15)

    def test_medium_preset_accepted(self):
        req = CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.40}}))
        assert req.parameters.ppi.min_confidence == pytest.approx(0.40)

    def test_high_preset_accepted(self):
        req = CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.70}}))
        assert req.parameters.ppi.min_confidence == pytest.approx(0.70)

    def test_very_high_preset_accepted(self):
        req = CreateAnalysisRequest(**_create({"ppi": {"min_confidence": 0.90}}))
        assert req.parameters.ppi.min_confidence == pytest.approx(0.90)

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


# ---------------------------------------------------------------------------
# Input size hard caps — plant_ids, compounds, targets
# ---------------------------------------------------------------------------

class TestInputSizeHardCaps:
    """plant_ids / compounds / targets must be rejected above their hard caps.

    Hard caps are literature-based (NP study scales):
      Plants:    max HARD_CAP_PLANTS            (20)  — Li S et al. (2014); Jiang Y et al. (2021)
      Compounds: max HARD_CAP_MANUAL_COMPOUNDS  (5000) — Zhou Y et al. (2019); 20 plants × ~250 cpds
      Targets:   max HARD_CAP_MANUAL_TARGETS    (5000) — Finan C et al. (2017) druggable proteome
    """

    # --- plant_ids ---

    def test_plant_ids_hard_cap_rejected(self):
        """plant_ids exceeding HARD_CAP_PLANTS should fail Pydantic validation."""
        import uuid

        too_many = [str(uuid.uuid4()) for _ in range(HARD_CAP_PLANTS + 1)]
        with pytest.raises(ValidationError):
            CreateAnalysisRequest(
                name="test",
                plant_ids=too_many,
                disease_id="d1",
            )

    def test_plant_ids_at_hard_cap_accepted(self):
        """plant_ids exactly at HARD_CAP_PLANTS should pass validation."""
        import uuid

        at_cap = [str(uuid.uuid4()) for _ in range(HARD_CAP_PLANTS)]
        req = CreateAnalysisRequest(
            name="test",
            plant_ids=at_cap,
            disease_id="d1",
        )
        assert len(req.plant_ids) == HARD_CAP_PLANTS

    def test_plant_ids_empty_accepted(self):
        """Empty plant_ids is valid (manual modes don't require plants)."""
        req = CreateAnalysisRequest(
            name="test",
            plant_ids=[],
            disease_id="d1",
        )
        assert req.plant_ids == []

    # --- InjectCompoundsRequest ---

    def test_compounds_hard_cap_rejected(self):
        """compounds list exceeding HARD_CAP_MANUAL_COMPOUNDS must fail validation."""
        too_many = ["CC"] * (HARD_CAP_MANUAL_COMPOUNDS + 1)
        with pytest.raises(ValidationError):
            InjectCompoundsRequest(compounds=too_many)

    def test_compounds_at_hard_cap_accepted(self):
        """compounds list exactly at HARD_CAP_MANUAL_COMPOUNDS must pass."""
        at_cap = ["CC"] * HARD_CAP_MANUAL_COMPOUNDS
        req = InjectCompoundsRequest(compounds=at_cap)
        assert len(req.compounds) == HARD_CAP_MANUAL_COMPOUNDS

    def test_compounds_below_min_rejected(self):
        """Empty compounds list must fail (min_length=1)."""
        with pytest.raises(ValidationError):
            InjectCompoundsRequest(compounds=[])

    # --- InjectTargetsRequest ---

    def test_targets_hard_cap_rejected(self):
        """targets list exceeding HARD_CAP_MANUAL_TARGETS must fail validation."""
        too_many = ["GENE"] * (HARD_CAP_MANUAL_TARGETS + 1)
        with pytest.raises(ValidationError):
            InjectTargetsRequest(targets=too_many)

    def test_targets_at_hard_cap_accepted(self):
        """targets list exactly at HARD_CAP_MANUAL_TARGETS must pass."""
        at_cap = ["GENE"] * HARD_CAP_MANUAL_TARGETS
        req = InjectTargetsRequest(targets=at_cap)
        assert len(req.targets) == HARD_CAP_MANUAL_TARGETS

    def test_targets_below_min_rejected(self):
        """Empty targets list must fail (min_length=1)."""
        with pytest.raises(ValidationError):
            InjectTargetsRequest(targets=[])


# ---------------------------------------------------------------------------
# _injected_disease_targets — hard cap via HARD_CAP_DISEASE_TARGETS
# ---------------------------------------------------------------------------

class TestInjectedDiseaseTargetsCap:
    """manual_disease_targets in CreateAnalysisRequest must be rejected above
    HARD_CAP_DISEASE_TARGETS.

    Disease targets from manual disease input (diseaseInputMode=manual_targets)
    are now a top-level request field (bypasses Open Targets). The cap mirrors the
    upper range of Open Targets single-disease associations (Ochoa et al. 2021).
    """

    def test_over_hard_cap_rejected(self):
        """manual_disease_targets exceeding HARD_CAP_DISEASE_TARGETS must fail."""
        too_many = [f"GENE{i}" for i in range(HARD_CAP_DISEASE_TARGETS + 1)]
        with pytest.raises(ValidationError):
            CreateAnalysisRequest(
                name="Test run", disease_id="disease-1",
                manual_disease_targets=too_many,
            )

    def test_at_hard_cap_accepted(self):
        """manual_disease_targets exactly at HARD_CAP_DISEASE_TARGETS must pass."""
        at_cap = [f"GENE{i}" for i in range(HARD_CAP_DISEASE_TARGETS)]
        req = CreateAnalysisRequest(
            name="Test run", disease_id="disease-1",
            manual_disease_targets=at_cap,
        )
        assert len(req.manual_disease_targets) == HARD_CAP_DISEASE_TARGETS

    def test_absent_key_accepted(self):
        """Missing manual_disease_targets (standard disease mode) must pass."""
        req = CreateAnalysisRequest(**_create({}))
        assert req.manual_disease_targets is None

    def test_empty_list_accepted(self):
        """Empty manual_disease_targets list must pass (validation deferred to Stage 4)."""
        req = CreateAnalysisRequest(
            name="Test run", disease_id="disease-1",
            manual_disease_targets=[],
        )
        assert req.manual_disease_targets == []


def test_create_analysis_requires_disease_id_unless_manual():
    from app.schemas.analysis import CreateAnalysisRequest
    import pytest
    from pydantic import ValidationError

    # Missing disease_id in standard mode → error
    with pytest.raises(ValidationError):
        CreateAnalysisRequest(name="x", plant_ids=["p1"], parameters={})

    # Manual disease-targets mode → disease_id may be None
    ok = CreateAnalysisRequest(
        name="x",
        plant_ids=["p1"],
        manual_disease_targets=["TP53"],
    )
    assert ok.disease_id is None

    # Standard mode with disease_id → valid
    ok2 = CreateAnalysisRequest(name="x", plant_ids=["p1"], disease_id="d1", parameters={})
    assert ok2.disease_id == "d1"


# ---------------------------------------------------------------------------
# UniProt accession format validation
# ---------------------------------------------------------------------------

from app.schemas.analysis import (
    AddUserTargetRequest,
    AddUserCompoundRequest,
    UNIPROT_ACCESSION_RE,
    GENE_SYMBOL_RE,
)


class TestUniprotAccessionFormat:
    """UniProt accession regex — HUPO-PSI standard.

    Pattern:
      ^[OPQ][0-9][A-Z0-9]{3}[0-9]$           (6-char legacy: O/P/Q + digit + 3 alphanums + digit)
      |^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$  (10-char new format: any non-O/P/Q letter...)
    """

    def test_valid_p04637(self):
        """P04637 — TP53 human canonical accession."""
        assert UNIPROT_ACCESSION_RE.match("P04637") is not None

    def test_valid_q9y6i3(self):
        """Q9Y6I3 — 6-char Q-type accession."""
        assert UNIPROT_ACCESSION_RE.match("Q9Y6I3") is not None

    def test_valid_o60341(self):
        """O60341 — O-type accession."""
        assert UNIPROT_ACCESSION_RE.match("O60341") is not None

    def test_invalid_all_digits_prefix(self):
        """123ABC — starts with digit, not a letter."""
        assert UNIPROT_ACCESSION_RE.match("123ABC") is None

    def test_invalid_gene_name(self):
        """gene_name — not an accession."""
        assert UNIPROT_ACCESSION_RE.match("gene_name") is None

    def test_invalid_too_short(self):
        """P1234 — only 5 chars, one short."""
        assert UNIPROT_ACCESSION_RE.match("P1234") is None

    def test_invalid_lowercase(self):
        """p04637 — lowercase first letter must fail."""
        assert UNIPROT_ACCESSION_RE.match("p04637") is None

    def test_add_user_target_uniprot_field_validates_format(self):
        """AddUserTargetRequest must reject invalid UniProt accession."""
        with pytest.raises(ValidationError, match="[Uu]ni[Pp]rot|accession|format"):
            AddUserTargetRequest(uniprot_id="123ABC")

    def test_add_user_target_uniprot_field_accepts_valid(self):
        """AddUserTargetRequest must accept a valid UniProt accession."""
        req = AddUserTargetRequest(uniprot_id="P04637")
        assert req.uniprot_id == "P04637"


# ---------------------------------------------------------------------------
# HGNC gene symbol validation
# ---------------------------------------------------------------------------

class TestGeneSymbolFormat:
    """HGNC gene symbol: uppercase letter start, 1–25 chars, A-Z0-9 and hyphen only.

    Pattern: ^[A-Z][A-Z0-9\\-]{0,24}$
    """

    def test_valid_tp53(self):
        assert GENE_SYMBOL_RE.match("TP53") is not None

    def test_valid_egfr(self):
        assert GENE_SYMBOL_RE.match("EGFR") is not None

    def test_valid_brca1(self):
        assert GENE_SYMBOL_RE.match("BRCA1") is not None

    def test_valid_hif1a_with_hyphen(self):
        assert GENE_SYMBOL_RE.match("HIF-1A") is not None

    def test_valid_hla_a(self):
        assert GENE_SYMBOL_RE.match("HLA-A") is not None

    def test_invalid_lowercase(self):
        assert GENE_SYMBOL_RE.match("tp53") is None

    def test_invalid_mixed_case(self):
        assert GENE_SYMBOL_RE.match("gene_lowercase") is None

    def test_invalid_starts_with_digit(self):
        assert GENE_SYMBOL_RE.match("1BADSTART") is None

    def test_invalid_empty(self):
        assert GENE_SYMBOL_RE.match("") is None

    def test_add_user_target_gene_symbol_field_validates_format(self):
        """AddUserTargetRequest must reject lowercase gene symbol."""
        with pytest.raises(ValidationError, match="[Gg]ene.symbol|[Hh][Gg][Nn][Cc]|format|uppercase"):
            AddUserTargetRequest(gene_symbol="tp53")

    def test_add_user_target_gene_symbol_field_accepts_valid(self):
        """AddUserTargetRequest must accept a valid gene symbol."""
        req = AddUserTargetRequest(gene_symbol="TP53")
        assert req.gene_symbol == "TP53"


# ---------------------------------------------------------------------------
# SMILES minimum validation
# ---------------------------------------------------------------------------

class TestSmilesMinimum:
    """SMILES minimal validator: length >= 3, printable ASCII only.

    Chemical correctness is PubChem's job — we only reject obviously malformed input.
    """

    def test_valid_ethanol(self):
        """CCO — ethanol, minimal valid SMILES."""
        req = AddUserCompoundRequest(smiles="CCO")
        assert req.smiles == "CCO"

    def test_valid_benzene(self):
        """c1ccccc1 — benzene aromatic SMILES."""
        req = AddUserCompoundRequest(smiles="c1ccccc1")
        assert req.smiles == "c1ccccc1"

    def test_valid_aspirin(self):
        """Aspirin SMILES — long valid string."""
        req = AddUserCompoundRequest(smiles="CC(=O)Oc1ccccc1C(=O)O")
        assert req.smiles == "CC(=O)Oc1ccccc1C(=O)O"

    def test_invalid_empty(self):
        """Empty string — too short (length < 3)."""
        with pytest.raises(ValidationError, match="[Ss][Mm][Ii][Ll][Ee][Ss]|[Ll]ength|[Tt]oo short|[Mm]inimum"):
            AddUserCompoundRequest(smiles="")

    def test_invalid_single_char(self):
        """'C' — only 1 char, below minimum length of 3."""
        with pytest.raises(ValidationError, match="[Ss][Mm][Ii][Ll][Ee][Ss]|[Ll]ength|[Tt]oo short|[Mm]inimum"):
            AddUserCompoundRequest(smiles="C")

    def test_invalid_non_ascii(self):
        """Null byte in SMILES — non-printable ASCII must be rejected."""
        with pytest.raises(ValidationError, match="[Ss][Mm][Ii][Ll][Ee][Ss]|[Aa][Ss][Cc][Ii][Ii]|printable"):
            AddUserCompoundRequest(smiles="\x00toxic")

    def test_invalid_two_chars(self):
        """'CC' — 2 chars, still below minimum."""
        with pytest.raises(ValidationError, match="[Ss][Mm][Ii][Ll][Ee][Ss]|[Ll]ength|[Tt]oo short|[Mm]inimum"):
            AddUserCompoundRequest(smiles="CC")
