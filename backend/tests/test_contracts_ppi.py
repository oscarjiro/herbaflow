from app import contracts


def test_ppi_defaults_match_lock():
    d = contracts.ppi_defaults()
    assert d == {
        "min_confidence": 0.4,
        "max_proteins": 2000,
        "allow_top_n_cap": False,
        "network_type": "functional",
    }


def test_ppi_dropped_community_resolution():
    assert "community_resolution" not in contracts.pipeline_param_bounds("ppi")


def test_ppi_min_confidence_enum_and_meta():
    b = contracts.pipeline_param_bounds("ppi")
    assert b["min_confidence"]["default"] == 0.4
    assert b["min_confidence"]["enum"] == [0.15, 0.4, 0.7, 0.9]
    assert b["network_type"]["default"] == "functional"
