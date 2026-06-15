"""The migration baseline's analysis_runs.mode CHECK must match the contract mode enum."""

import re
from pathlib import Path

from app import contracts

_BASELINE = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260608000005_baseline_operational.sql"
)


def _mode_check_values() -> set[str]:
    sql = _BASELINE.read_text(encoding="utf-8")
    # Match: mode ... check (mode in ('auto', 'guided'))  (case-insensitive, flexible whitespace)
    m = re.search(r"mode\s+in\s*\(([^)]*)\)", sql, flags=re.IGNORECASE)
    assert m, "mode CHECK not found in the operational baseline migration"
    return {v.strip().strip("'\"") for v in m.group(1).split(",")}


def test_mode_check_matches_contract():
    assert _mode_check_values() == set(contracts.modes())


def test_adme_defaults_agree_with_contract_properties() -> None:
    """adme_defaults() must equal the ``default`` field of every adme property in the contract."""
    props = contracts.pipeline_parameters()["adme"]["properties"]
    expected = {name: spec["default"] for name, spec in props.items()}
    assert contracts.adme_defaults() == expected


def test_create_schema_cap_matches_contract() -> None:
    from app.schemas.analysis import AnalysisCreate

    field = AnalysisCreate.model_fields["plant_ids"]
    maxes = [m for m in field.metadata if getattr(m, "max_length", None) is not None]
    assert maxes and maxes[0].max_length == contracts.max_plants()


def test_target_defaults_match_contract():
    d = contracts.target_defaults()
    assert d == {"min_pchembl": 5.0, "min_assay_confidence": 7}
    assert "human_only" not in d
    meta = contracts.target_param_meta()
    assert meta["min_pchembl"]["recommended_max"] == 7.0
    assert meta["min_assay_confidence"]["max"] == 9


def test_disease_targets_defaults_match_contract():
    d = contracts.disease_targets_defaults()
    assert d == {"min_score": 0.3}
    meta = contracts.disease_targets_param_meta()
    assert meta["min_score"]["min"] == 0
    assert meta["min_score"]["max"] == 1
    assert meta["min_score"]["recommended_min"] == 0.1
    assert meta["min_score"]["recommended_max"] == 0.5
    assert meta["min_score"]["default"] == 0.3
    assert meta["min_score"]["description"]


def test_ppi_defaults_match_contract():
    d = contracts.ppi_defaults()
    assert d == {
        "min_confidence": 0.4,
        "max_proteins": 2000,
        "allow_top_n_cap": False,
        "network_type": "functional",
    }
    assert "community_resolution" not in contracts.pipeline_param_bounds("ppi")


def test_ppi_param_meta_matches_contract():
    meta = contracts.ppi_param_meta()
    assert meta["min_confidence"]["default"] == 0.4
    assert meta["min_confidence"]["enum"] == [0.15, 0.4, 0.7, 0.9]
    assert meta["min_confidence"]["description"]
    assert meta["max_proteins"]["default"] == 2000
    assert meta["max_proteins"]["min"] == 50
    assert meta["max_proteins"]["max"] == 2000
    assert meta["max_proteins"]["recommended_min"] == 200
    assert meta["max_proteins"]["recommended_max"] == 2000
    assert meta["allow_top_n_cap"]["default"] is False
    assert meta["network_type"]["default"] == "functional"
    assert meta["network_type"]["enum"] == ["functional", "physical"]
    assert meta["network_type"]["description"]


def test_hub_genes_defaults_match_contract():
    d = contracts.hub_genes_defaults()
    assert d == {"top_n": 20}
    assert "use_hub_bottleneck" not in d
    assert "composite_weight" not in d
    meta = contracts.hub_genes_param_meta()
    assert set(meta.keys()) == {"top_n"}
    assert meta["top_n"]["min"] == 1
    assert meta["top_n"]["max"] == 200
    assert meta["top_n"]["default"] == 20


def test_plant_input_modes_match_contract() -> None:
    from app import contracts

    assert contracts.plant_input_modes() == ("selection", "manual_compounds", "manual_targets")
    assert contracts.default_plant_input_mode() == "selection"


def test_disease_input_modes_match_contract() -> None:
    from app import contracts

    assert contracts.disease_input_modes() == ("selection", "manual_disease_targets")
    assert contracts.default_disease_input_mode() == "selection"


def test_enrichment_defaults_match_contract():
    d = contracts.enrichment_defaults()
    assert d == {
        "significance_threshold": 0.05,
        "sources": ["GO:BP", "GO:MF", "GO:CC", "KEGG"],
        "correction": "fdr",
        "min_term_size": 5,
        "no_iea": False,
    }
    meta = contracts.enrichment_param_meta()
    assert meta["significance_threshold"]["default"] == 0.05
    assert meta["correction"]["enum"] == ["fdr", "g_SCS", "bonferroni"]
    assert meta["min_term_size"]["min"] == 1
    assert meta["sources"]["default"] == ["GO:BP", "GO:MF", "GO:CC", "KEGG"]
    assert meta["no_iea"]["default"] is False
    # The allowed-values enum is nested inside sources.items (array schema) — read via raw bounds.
    sources_spec = contracts.pipeline_param_bounds("enrichment")["sources"]
    assert sources_spec["items"]["enum"] == ["GO:BP", "GO:MF", "GO:CC", "KEGG", "REAC", "WP"]
