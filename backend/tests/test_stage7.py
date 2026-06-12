from app.pipeline.stages import stage7


def _s6(nodes, edges):
    return {
        "state": "computed",
        "nodes": [
            {"gene_symbol": g, "target_id": t, "uniprot_accession": a, "string_id": None}
            for (g, t, a) in nodes
        ],
        "edges": [{"source": s, "target": d, "confidence": c} for (s, d, c) in edges],
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def test_ranks_hub_by_composite_with_individual_centralities():
    # star graph: HUB connects to A,B,C -> HUB is the clear top hub/bottleneck.
    nodes = [("HUB", "t0", "P0"), ("A", "t1", "P1"), ("B", "t2", "P2"), ("C", "t3", "P3")]
    edges = [("HUB", "A", 0.9), ("HUB", "B", 0.8), ("HUB", "C", 0.7)]
    out = stage7.compute(_s6(nodes, edges), top_n=20, use_hub_bottleneck=True, composite_weight=0.5)
    assert out["state"] == "computed"
    assert out["hubs"][0]["gene_symbol"] == "HUB"
    top = out["hubs"][0]
    # all four individual centralities are reported alongside the composite
    for key in ("degree", "betweenness", "closeness", "eigenvector", "composite"):
        assert key in top
    assert top["target_id"] == "t0"
    assert top["source_url"] == "https://www.uniprot.org/uniprotkb/P0/entry"
    assert out["ranking_metric"] == "hub_bottleneck_composite"
    assert out["normalization"] == "min_max"
    assert out["node_count"] == 4


def test_top_n_caps_the_hub_list():
    nodes = [(f"G{i}", f"t{i}", f"P{i}") for i in range(5)]
    edges = [("G0", "G1", 0.9), ("G1", "G2", 0.9), ("G2", "G3", 0.9), ("G3", "G4", 0.9)]
    out = stage7.compute(_s6(nodes, edges), top_n=3, use_hub_bottleneck=True, composite_weight=0.5)
    assert len(out["hubs"]) == 3
    assert [h["rank"] for h in out["hubs"]] == [1, 2, 3]


def test_top_n_greater_than_nodes_returns_all():
    nodes = [("A", "t1", "P1"), ("B", "t2", "P2")]
    edges = [("A", "B", 0.9)]
    out = stage7.compute(_s6(nodes, edges), top_n=50, use_hub_bottleneck=True, composite_weight=0.5)
    assert len(out["hubs"]) == 2


def test_deterministic_tie_break_by_gene_symbol():
    # an edgeless 2-node graph: all centralities 0 -> tie -> alphabetical gene order is stable.
    out = stage7.compute(
        _s6([("ZED", "t2", "P2"), ("ABE", "t1", "P1")], []),
        top_n=20,
        use_hub_bottleneck=True,
        composite_weight=0.5,
    )
    assert [h["gene_symbol"] for h in out["hubs"]] == ["ABE", "ZED"]
    assert "network_too_small" in out["flags"]


def test_plain_degree_ranking_when_composite_off():
    nodes = [("HUB", "t0", "P0"), ("A", "t1", "P1"), ("B", "t2", "P2")]
    edges = [("HUB", "A", 0.9), ("HUB", "B", 0.8)]
    out = stage7.compute(
        _s6(nodes, edges), top_n=20, use_hub_bottleneck=False, composite_weight=0.5
    )
    assert out["ranking_metric"] == "degree"
    assert out["hubs"][0]["gene_symbol"] == "HUB"


def test_empty_network_is_count_zero_with_flag():
    out = stage7.compute(_s6([], []), top_n=20, use_hub_bottleneck=True, composite_weight=0.5)
    assert out["count"] == 0 and out["hubs"] == []
    assert "network_too_small" in out["flags"]
