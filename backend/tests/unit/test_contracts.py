# backend/tests/unit/test_contracts.py
from app.contracts import ANALYSIS_MODES, PIPELINE_PARAM_FIELDS


def test_analysis_modes_unchanged():
    assert set(ANALYSIS_MODES) == {"auto", "guided"}


def test_pipeline_param_fields_groups_and_members():
    assert set(PIPELINE_PARAM_FIELDS) == {
        "adme", "target", "disease_targets", "ppi", "hub_genes", "enrichment",
    }
    assert PIPELINE_PARAM_FIELDS["target"] == {
        "min_pchembl", "human_only", "min_assay_confidence",
    }
    assert PIPELINE_PARAM_FIELDS["ppi"] == {"min_confidence", "community_resolution"}
    assert "sources" in PIPELINE_PARAM_FIELDS["enrichment"]
