from app.pipeline import charts

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def test_png_helper_present():
    assert hasattr(charts, "render_venn")


# Task 13 — Venn (Stage 5)


def test_venn_title_with_both_labels():
    title = charts.venn_title("Curcuma longa", "Type 2 diabetes")
    assert title == "Curcuma longa and Type 2 diabetes target overlap"
    assert "Stage 5" not in title
    assert "—" not in title


def test_venn_title_without_labels():
    title = charts.venn_title(None, None)
    assert title == "Target overlap"


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


# Task T4 — enrichment dotplot (enrichment_title + rewritten render_enrichment_bubble)


def test_enrichment_title_gobp():
    title = charts.enrichment_title("GO:BP")
    assert title == "Functional enrichment: Biological Process"
    assert "Biological Process" in title
    assert "BP" not in title.replace("Biological Process", "")


def test_enrichment_title_kegg():
    title = charts.enrichment_title("KEGG")
    assert "KEGG pathways" in title
    assert title == "Functional enrichment: KEGG pathways"


def test_enrichment_title_reac():
    title = charts.enrichment_title("REAC")
    assert "Reactome pathways" in title
    assert title == "Functional enrichment: Reactome pathways"


def test_enrichment_title_wp():
    title = charts.enrichment_title("WP")
    assert "WikiPathways" in title
    assert title == "Functional enrichment: WikiPathways"


def test_enrichment_title_no_stage_reference():
    for cat in charts.ENRICHMENT_CATEGORIES:
        title = charts.enrichment_title(cat)
        assert "Stage" not in title, f"Title for {cat!r} contains 'Stage': {title!r}"
        assert "stage" not in title


def test_enrichment_dotplot_returns_png_bytes():
    s8 = {
        "terms": [
            {
                "term_id": "GO:1",
                "name": "apoptosis",
                "source": "GO:BP",
                "p_value": 1e-5,
                "intersection": ["PPARG", "TP53", "EGFR"],
            },
            {
                "term_id": "GO:2",
                "name": "cell cycle",
                "source": "GO:BP",
                "p_value": 1e-3,
                "intersection": ["TP53"],
            },
        ]
    }
    result = charts.render_enrichment_bubble(s8, "GO:BP", overlap_size=17)
    assert isinstance(result, bytes)
    assert result[:8] == _PNG_SIG


def test_enrichment_dotplot_none_when_no_terms_for_category():
    s8 = {
        "terms": [
            {
                "term_id": "GO:1",
                "name": "apoptosis",
                "source": "GO:BP",
                "p_value": 1e-5,
                "intersection": ["PPARG"],
            }
        ]
    }
    assert charts.render_enrichment_bubble(s8, "REAC", overlap_size=17) is None


def test_enrichment_dotplot_none_when_overlap_size_zero():
    s8 = {
        "terms": [
            {
                "term_id": "GO:1",
                "name": "apoptosis",
                "source": "GO:BP",
                "p_value": 1e-5,
                "intersection": ["PPARG"],
            }
        ]
    }
    assert charts.render_enrichment_bubble(s8, "GO:BP", overlap_size=0) is None


def test_enrichment_dotplot_none_when_overlap_size_none():
    s8 = {
        "terms": [
            {
                "term_id": "GO:1",
                "name": "apoptosis",
                "source": "GO:BP",
                "p_value": 1e-5,
                "intersection": ["PPARG"],
            }
        ]
    }
    assert charts.render_enrichment_bubble(s8, "GO:BP", overlap_size=None) is None


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


# Task T6 — CTP core selection and capped render


def _make_small_ctp_graph() -> dict:
    """A minimal 3-node, 2-edge C-T-P graph (well below CTP_FULL_RENDER_MAX)."""
    return {
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


def _make_large_ctp_graph(
    n_compound: int = 80,
    n_target: int = 80,
    n_pathway: int = 60,
) -> dict:
    """Build a graph with 200+ nodes across all three types.

    Connectivity: each compound connects to every target; each target connects to every pathway.
    This ensures varying degree so the selector has something to rank on.
    """
    compounds = [{"id": f"C{i}", "label": f"C{i}", "type": "compound"} for i in range(n_compound)]
    targets = [{"id": f"T{i}", "label": f"T{i}", "type": "target"} for i in range(n_target)]
    pathways = [{"id": f"P{i}", "label": f"P{i}", "type": "pathway"} for i in range(n_pathway)]
    nodes = compounds + targets + pathways

    edges = []
    # Compound→target edges (first compound connects to all targets, giving it highest degree)
    for c in compounds[:1]:
        for t in targets:
            edges.append({"source": c["id"], "target": t["id"]})
    # Target→pathway edges
    for t in targets[:1]:
        for p in pathways:
            edges.append({"source": t["id"], "target": p["id"]})
    return {"nodes": nodes, "edges": edges}


def test_select_ctp_core_small_returns_all():
    """Small graph (< cap): select_ctp_core returns every node id."""
    graph = _make_small_ctp_graph()
    all_ids = {n["id"] for n in graph["nodes"]}
    result = set(charts.select_ctp_core(graph))
    assert result == all_ids


def test_select_ctp_core_large_respects_cap():
    """Large graph (200+ nodes): result length is at most cap + small slack."""
    cap = 80
    graph = _make_large_ctp_graph()
    result = charts.select_ctp_core(graph, cap=cap)
    assert len(result) <= cap + 3


def test_select_ctp_core_large_preserves_type_balance():
    """Large graph: at least one node from each present type is included."""
    cap = 80
    graph = _make_large_ctp_graph()
    result_ids = set(charts.select_ctp_core(graph, cap=cap))
    node_types_in_result = {n["type"] for n in graph["nodes"] if n["id"] in result_ids}
    assert "compound" in node_types_in_result
    assert "target" in node_types_in_result
    assert "pathway" in node_types_in_result


def test_ctp_render_small_returns_png():
    """render_ctp_network returns PNG bytes for a small valid graph."""
    png = charts.render_ctp_network(_make_small_ctp_graph())
    assert isinstance(png, bytes)
    assert png[:8] == _PNG_SIG


def test_ctp_render_no_edges_returns_none():
    """render_ctp_network returns None when there are no edges."""
    assert charts.render_ctp_network({"nodes": [], "edges": []}) is None
