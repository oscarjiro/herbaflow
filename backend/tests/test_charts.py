from app.pipeline import charts

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def test_png_helper_present():
    assert hasattr(charts, "render_venn")


# Task 13 — Venn (Stage 5)


def test_venn_renders_png():
    out = charts.render_venn(
        {"count": 17, "compound_target_count": 180, "disease_target_count": 911}
    )
    assert out is not None and out.startswith(_PNG_SIG)


def test_venn_none_when_empty():
    assert (
        charts.render_venn({"count": 0, "compound_target_count": 0, "disease_target_count": 0})
        is None
    )


# Task 14 — Hub bar (Stage 7)


def test_hub_bar_renders():
    out = charts.render_hub_bar(
        {
            "hubs": [
                {"gene_symbol": "PPARG", "composite": 0.9},
                {"gene_symbol": "TP53", "composite": 0.4},
            ]
        }
    )
    assert out is not None and out.startswith(_PNG_SIG)


def test_hub_bar_none_when_empty():
    assert charts.render_hub_bar({"hubs": []}) is None


def test_hub_bar_title_states_top_n():
    s7 = {"hubs": [{"gene_symbol": "A", "composite": 1.0}, {"gene_symbol": "B", "composite": 0.2}]}
    png = charts.render_hub_bar(s7)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# Task 15 — Enrichment bubble per category (Stage 8)


_TERMS = {
    "terms": [
        {
            "term_id": "GO:1",
            "name": "apoptosis",
            "source": "GO:BP",
            "p_value": 1e-4,
            "intersection": ["PPARG", "TP53"],
        },
        {
            "term_id": "KEGG:1",
            "name": "insulin",
            "source": "KEGG",
            "p_value": 1e-3,
            "intersection": ["PPARG"],
        },
    ]
}


def test_bubble_per_category():
    assert charts.render_enrichment_bubble(_TERMS, "GO:BP", overlap_size=17) is not None
    assert charts.render_enrichment_bubble(_TERMS, "GO:BP", overlap_size=17).startswith(_PNG_SIG)


def test_bubble_none_when_category_empty():
    assert charts.render_enrichment_bubble(_TERMS, "REAC", overlap_size=17) is None


def test_enrichment_dotplot_uses_gene_ratio_and_returns_png():
    s8 = {
        "terms": [
            {
                "term_id": "GO:1",
                "name": "x",
                "source": "GO:BP",
                "p_value": 1e-4,
                "intersection": ["A", "B"],
            },
            {
                "term_id": "GO:2",
                "name": "y",
                "source": "GO:BP",
                "p_value": 1e-2,
                "intersection": ["A"],
            },
        ]
    }
    png = charts.render_enrichment_bubble(s8, "GO:BP", overlap_size=17)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_enrichment_empty_category_returns_none():
    assert charts.render_enrichment_bubble({"terms": []}, "KEGG", overlap_size=17) is None


def test_enrichment_categories_list():
    assert charts.ENRICHMENT_CATEGORIES == ["GO:BP", "GO:MF", "GO:CC", "KEGG", "REAC", "WP"]
    assert charts.category_slug("GO:BP") == "BP"


# Task 9 — concentric C-T-P network


def test_ctp_network_renders_png_with_typed_nodes():
    graph = {
        "nodes": [
            {"id": "CURCUMIN", "label": "CURCUMIN", "type": "compound"},
            {"id": "PPARG", "label": "PPARG", "type": "target"},
            {"id": "GO:1", "label": "blood circulation", "type": "pathway"},
        ],
        "edges": [
            {"source": "CURCUMIN", "target": "PPARG"},
            {"source": "PPARG", "target": "GO:1"},
        ],
    }
    png = charts.render_ctp_network(graph)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_ctp_network_no_edges_returns_none():
    assert charts.render_ctp_network({"nodes": [], "edges": []}) is None


# Task 10 — dedicated PPI network


def test_ppi_network_marks_isolated_and_colours_by_hub():
    graph = {
        "nodes": [{"id": "A"}, {"id": "B"}, {"id": "VDR"}],
        "edges": [{"source": "A", "target": "B", "confidence": 0.9}],
    }
    hubs = {"A": 1.0, "B": 0.5, "VDR": 0.0}
    png = charts.render_ppi_network(graph, hub_scores=hubs, min_confidence=0.4)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_ppi_network_no_nodes_returns_none():
    assert (
        charts.render_ppi_network({"nodes": [], "edges": []}, hub_scores={}, min_confidence=0.4)
        is None
    )
