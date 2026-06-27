from app import contracts


def test_hub_genes_defaults_match_lock():
    assert contracts.hub_genes_defaults() == {
        "top_n": 20,
    }


def test_enrichment_defaults_match_lock():
    assert contracts.enrichment_defaults() == {
        "significance_threshold": 0.05,
        "sources": ["GO:BP", "GO:MF", "GO:CC", "KEGG"],
        "correction": "fdr",
        "min_term_size": 5,
        "no_iea": False,
    }


def test_enrichment_correction_enum_is_api_verbatim():
    bounds = contracts.pipeline_param_bounds("enrichment")
    assert bounds["correction"]["enum"] == ["fdr", "g_SCS", "bonferroni"]


def test_hub_genes_param_bounds():
    b = contracts.pipeline_param_bounds("hub_genes")
    assert b["top_n"]["minimum"] == 1 and b["top_n"]["maximum"] == 200
    assert set(b.keys()) == {"top_n"}
    assert b["top_n"]["default"] == 20
