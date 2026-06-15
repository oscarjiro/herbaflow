import pytest

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


def test_ranks_hub_by_mcc_with_individual_centralities():
    # K4 on {A,B,C,D} (all interconnected) + a pendant E on A.
    # Clique {A,B,C,D} -> (4-1)! = 6 to each of A,B,C,D; A also in {A,E} (size 2 -> 1).
    nodes = [
        ("A", "t0", "P0"),
        ("B", "t1", "P1"),
        ("C", "t2", "P2"),
        ("D", "t3", "P3"),
        ("E", "t4", "P4"),
    ]
    edges = [
        ("A", "B", 0.9),
        ("A", "C", 0.9),
        ("A", "D", 0.9),
        ("B", "C", 0.9),
        ("B", "D", 0.9),
        ("C", "D", 0.9),
        ("A", "E", 0.9),
    ]
    out = stage7.compute(_s6(nodes, edges), top_n=20)
    assert out["state"] == "computed"
    assert out["ranking_metric"] == "mcc"
    top = out["hubs"][0]
    assert top["gene_symbol"] == "A"
    assert top["mcc"] == 7  # 6 (K4) + 1 (edge A-E)
    by_gene = {h["gene_symbol"]: h for h in out["hubs"]}
    assert by_gene["B"]["mcc"] == 6  # only in the K4 clique
    assert by_gene["E"]["mcc"] == 1  # pendant: one size-2 clique
    for key in ("degree", "betweenness", "closeness", "eigenvector", "mcc"):
        assert key in top
    assert top["target_id"] == "t0"
    assert top["source_url"] == "https://www.uniprot.org/uniprotkb/P0/entry"
    assert out["node_count"] == 5
    assert "composite" not in top
    assert "composite_weight" not in out
    assert "normalization" not in out


def test_isolated_node_scores_zero():
    # A-B edge; C isolated. C's only clique is the singleton -> skipped -> MCC 0 (== degree 0).
    out = stage7.compute(
        _s6([("A", "t1", "P1"), ("B", "t2", "P2"), ("C", "t3", "P3")], [("A", "B", 0.9)]),
        top_n=20,
    )
    by_gene = {h["gene_symbol"]: h for h in out["hubs"]}
    assert by_gene["C"]["mcc"] == 0
    assert by_gene["A"]["mcc"] == 1  # single edge -> (2-1)! = 1
    assert out["hubs"][-1]["gene_symbol"] == "C"  # mcc 0 ranks last


def test_mcc_equals_degree_when_neighbours_not_interconnected():
    # star: HUB-A, HUB-B, HUB-C; A,B,C not interconnected -> three size-2 maximal cliques.
    out = stage7.compute(
        _s6(
            [("HUB", "t0", "P0"), ("A", "t1", "P1"), ("B", "t2", "P2"), ("C", "t3", "P3")],
            [("HUB", "A", 0.9), ("HUB", "B", 0.8), ("HUB", "C", 0.7)],
        ),
        top_n=20,
    )
    by_gene = {h["gene_symbol"]: h for h in out["hubs"]}
    assert by_gene["HUB"]["mcc"] == 3  # 3 * (2-1)! = 3 == degree count
    assert out["hubs"][0]["gene_symbol"] == "HUB"


def test_triangle_each_node_mcc_two():
    out = stage7.compute(
        _s6(
            [("A", "t1", "P1"), ("B", "t2", "P2"), ("C", "t3", "P3")],
            [("A", "B", 0.9), ("B", "C", 0.9), ("A", "C", 0.9)],
        ),
        top_n=20,
    )
    assert all(h["mcc"] == 2 for h in out["hubs"])  # (3-1)! = 2


def test_top_n_caps_the_hub_list():
    nodes = [(f"G{i}", f"t{i}", f"P{i}") for i in range(5)]
    edges = [("G0", "G1", 0.9), ("G1", "G2", 0.9), ("G2", "G3", 0.9), ("G3", "G4", 0.9)]
    out = stage7.compute(_s6(nodes, edges), top_n=3)
    assert len(out["hubs"]) == 3
    assert [h["rank"] for h in out["hubs"]] == [1, 2, 3]


def test_top_n_greater_than_nodes_returns_all():
    out = stage7.compute(_s6([("A", "t1", "P1"), ("B", "t2", "P2")], [("A", "B", 0.9)]), top_n=50)
    assert len(out["hubs"]) == 2


def test_deterministic_tie_break():
    # edgeless 2-node graph: all mcc 0, degree 0 -> tie -> alphabetical gene order is stable.
    out = stage7.compute(_s6([("ZED", "t2", "P2"), ("ABE", "t1", "P1")], []), top_n=20)
    assert [h["gene_symbol"] for h in out["hubs"]] == ["ABE", "ZED"]
    assert "network_too_small" in out["flags"]


def test_empty_network_is_count_zero_with_flag():
    out = stage7.compute(_s6([], []), top_n=20)
    assert out["count"] == 0 and out["hubs"] == []
    assert out["ranking_metric"] == "mcc"
    assert "network_too_small" in out["flags"]


@pytest.mark.asyncio
async def test_run_reads_stage6_results():
    run = type("R", (), {})()
    run.stage_results = {
        "6": {
            "state": "computed",
            "nodes": [
                {
                    "gene_symbol": "HUB",
                    "target_id": "t0",
                    "uniprot_accession": "P0",
                    "string_id": None,
                },
                {
                    "gene_symbol": "A",
                    "target_id": "t1",
                    "uniprot_accession": "P1",
                    "string_id": None,
                },
            ],
            "edges": [{"source": "HUB", "target": "A", "confidence": 0.9}],
            "node_count": 2,
            "edge_count": 1,
        },
    }
    run.parameters = {"hub_genes": {"top_n": 20}}
    out = await stage7.run(None, run)
    assert out["count"] == 2
    assert out["ranking_metric"] == "mcc"
