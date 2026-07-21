from app import contracts


def test_ppi_defaults_match_lock():
    d = contracts.ppi_defaults()
    assert d == {
        "min_confidence": 0.4,
        "network_type": "functional",
    }


def test_ppi_dropped_community_resolution():
    assert "community_resolution" not in contracts.pipeline_param_bounds("ppi")


def test_ppi_has_no_self_imposed_protein_cap():
    """STRING imposes no identifier count limit when species is set; we always send 9606."""
    b = contracts.pipeline_param_bounds("ppi")
    assert "max_proteins" not in b
    assert "allow_top_n_cap" not in b


def test_ppi_min_confidence_enum_and_meta():
    b = contracts.pipeline_param_bounds("ppi")
    assert b["min_confidence"]["default"] == 0.4
    assert b["min_confidence"]["enum"] == [0.15, 0.4, 0.7, 0.9]
    assert b["network_type"]["default"] == "functional"
