import networkx as nx
from analysis.stages.stage7_hub_genes import compute_hub_genes, compute_community_centrality


def make_star_graph() -> nx.Graph:
    """Star graph: 'center' connected to 4 leaves. Center is clearly the hub."""
    G = nx.Graph()
    G.add_edges_from([("center", "a"), ("center", "b"), ("center", "c"), ("center", "d")])
    return G


def test_hub_identified():
    G = make_star_graph()
    result = compute_hub_genes(G, top_n=5)
    assert result["ranked"][0]["gene_symbol"] == "center"


def test_all_4_metrics_present():
    G = make_star_graph()
    result = compute_hub_genes(G, top_n=5)
    top = result["ranked"][0]
    assert "degree" in top
    assert "betweenness" in top
    assert "closeness" in top
    assert "eigenvector" in top


def test_hub_bottleneck_flagged():
    G = make_star_graph()
    result = compute_hub_genes(G, top_n=5)
    center = next(r for r in result["ranked"] if r["gene_symbol"] == "center")
    assert center["is_hub"] is True
    assert center["is_hub_bottleneck"] is True


def test_top_n_respected():
    G = nx.complete_graph(10)
    nx.relabel_nodes(G, {i: f"gene_{i}" for i in range(10)}, copy=False)
    result = compute_hub_genes(G, top_n=3)
    assert len(result["ranked"]) == 3


def test_empty_graph():
    G = nx.Graph()
    result = compute_hub_genes(G, top_n=20)
    assert result["ranked"] == []


def test_degree_normalized_between_0_and_1():
    """Degree in HubGeneResult must be normalized 0–1."""
    G = nx.Graph()
    G.add_edges_from([('A', 'B'), ('B', 'C'), ('A', 'C'), ('C', 'D')])
    # A, B, C, D — max degree = 3 (node C)
    # Normalized: C's degree = 3/(4-1) = 1.0

    result = compute_hub_genes(G, top_n=4, use_hub_bottleneck=False)

    for gene in result['ranked']:
        assert 0.0 <= gene['degree'] <= 1.0, f"Degree {gene['degree']} out of [0,1]"


def test_no_null_score_fields_in_ranked():
    """disease_association_score / compound_support_score / final_score must never
    appear as null keys in the ranked dicts stored inside stage_results JSONB."""
    G = make_star_graph()
    result = compute_hub_genes(G, top_n=5)
    forbidden = {"disease_association_score", "compound_support_score", "final_score"}
    for entry in result["ranked"]:
        assert not forbidden.intersection(entry.keys()), (
            f"Null score fields found in ranked entry: {entry}"
        )
        assert {"gene_symbol", "degree", "betweenness", "closeness", "eigenvector", "is_hub"}.issubset(entry.keys()), (
            f"Expected core fields missing from ranked entry: {entry}"
        )


# ── Stage 7 run() wrapper ──────────────────────────────────────────────────────

from unittest.mock import AsyncMock, MagicMock
from analysis.stages import stage7_hub_genes
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun


def make_stage7_run(edges=None):
    run = MagicMock(spec=AnalysisRun)
    run.analysis_id = "test-analysis-id"
    run.parameters = {}
    run.stage_results = {"stage_6": {"edges": edges or []}}
    return run


async def test_stage7_run_empty_edges_returns_empty_ranked():
    run = make_stage7_run(edges=[])
    config = PipelineConfig()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    session.exec = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.commit = AsyncMock()

    result = await stage7_hub_genes.run(run, config, session)

    assert result["ranked"] == []


async def test_stage7_run_reconstructs_graph_from_edges():
    edges = [
        {"source": "AKT1", "target": "TNF", "combined_score": 0.7},
        {"source": "AKT1", "target": "TP53", "combined_score": 0.6},
        {"source": "TNF", "target": "TP53", "combined_score": 0.5},
    ]
    run = make_stage7_run(edges=edges)
    config = PipelineConfig()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    session.exec = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.commit = AsyncMock()

    result = await stage7_hub_genes.run(run, config, session)

    ranked_genes = [r["gene_symbol"] for r in result["ranked"]]
    assert len(ranked_genes) == 3
    assert set(ranked_genes) == {"AKT1", "TNF", "TP53"}


# ── compute_community_centrality ──────────────────────────────────────────────


def make_two_community_graph():
    """Two cliques of 4 nodes each, sparsely connected across communities."""
    G = nx.Graph()
    # Community 0: GENE1–GENE4 densely connected
    G.add_edges_from([
        ("GENE1", "GENE2"), ("GENE1", "GENE3"), ("GENE1", "GENE4"),
        ("GENE2", "GENE3"), ("GENE2", "GENE4"), ("GENE3", "GENE4"),
    ])
    # Community 1: GENE5–GENE8 densely connected
    G.add_edges_from([
        ("GENE5", "GENE6"), ("GENE5", "GENE7"), ("GENE5", "GENE8"),
        ("GENE6", "GENE7"), ("GENE6", "GENE8"), ("GENE7", "GENE8"),
    ])
    # Sparse inter-community edge
    G.add_edge("GENE1", "GENE5")
    gene_to_community = {
        "GENE1": 0, "GENE2": 0, "GENE3": 0, "GENE4": 0,
        "GENE5": 1, "GENE6": 1, "GENE7": 1, "GENE8": 1,
    }
    return G, gene_to_community


def test_per_community_centrality_computed():
    """Per-community centrality should identify hub genes within each community."""
    G, gene_to_community = make_two_community_graph()

    community_hubs = compute_community_centrality(G, gene_to_community)

    assert 0 in community_hubs
    assert 1 in community_hubs
    assert len(community_hubs[0]) > 0
    assert len(community_hubs[1]) > 0


def test_per_community_centrality_required_fields():
    """Each hub entry must contain all required centrality fields."""
    G, gene_to_community = make_two_community_graph()

    community_hubs = compute_community_centrality(G, gene_to_community)

    top_hub_c0 = community_hubs[0][0]
    assert "gene_symbol" in top_hub_c0
    assert "community_id" in top_hub_c0
    assert "community_degree" in top_hub_c0
    assert "community_betweenness" in top_hub_c0
    assert "community_closeness" in top_hub_c0
    assert "community_eigenvector" in top_hub_c0
    assert "community_size" in top_hub_c0
    assert top_hub_c0["community_id"] == 0
    assert top_hub_c0["community_size"] == 4
    assert top_hub_c0["community_degree"] > 0


def test_per_community_centrality_correct_community_size():
    """community_size must reflect only the nodes in that community, not the full graph."""
    G, gene_to_community = make_two_community_graph()

    community_hubs = compute_community_centrality(G, gene_to_community)

    for hub in community_hubs[0]:
        assert hub["community_size"] == 4
    for hub in community_hubs[1]:
        assert hub["community_size"] == 4


def test_per_community_centrality_single_node():
    """Community with only 1 node returns empty list (no meaningful centrality)."""
    G = nx.Graph()
    G.add_node("GENE1")
    G.add_edge("GENE2", "GENE3")
    gene_to_community = {"GENE1": 0, "GENE2": 1, "GENE3": 1}

    community_hubs = compute_community_centrality(G, gene_to_community)

    assert community_hubs[0] == []
    assert len(community_hubs[1]) == 2


def test_per_community_centrality_ranked_descending():
    """Hubs must be ranked by community_degree descending."""
    G, gene_to_community = make_two_community_graph()

    community_hubs = compute_community_centrality(G, gene_to_community)

    for cid, hubs in community_hubs.items():
        degrees = [h["community_degree"] for h in hubs]
        assert degrees == sorted(degrees, reverse=True), (
            f"Community {cid} hubs not ranked descending by community_degree"
        )


def test_per_community_centrality_degree_normalized():
    """community_degree must be normalized 0–1 within the subgraph."""
    G, gene_to_community = make_two_community_graph()

    community_hubs = compute_community_centrality(G, gene_to_community)

    for cid, hubs in community_hubs.items():
        for hub in hubs:
            assert 0.0 <= hub["community_degree"] <= 1.0, (
                f"community_degree {hub['community_degree']} out of [0,1] in community {cid}"
            )


def test_per_community_centrality_empty_graph():
    """Empty graph with no nodes returns empty dict."""
    G = nx.Graph()
    community_hubs = compute_community_centrality(G, {})
    assert community_hubs == {}


def test_per_community_centrality_no_community_assignments():
    """Nodes with no community assignment are silently excluded."""
    G = nx.Graph()
    G.add_edges_from([("A", "B"), ("B", "C")])
    gene_to_community = {}  # no assignments

    community_hubs = compute_community_centrality(G, gene_to_community)

    assert community_hubs == {}


def test_stage7_run_includes_community_hubs():
    """run() result must contain community_hubs key."""
    import asyncio
    edges = [
        {"source": "AKT1", "target": "TNF", "combined_score": 0.7},
        {"source": "AKT1", "target": "TP53", "combined_score": 0.6},
        {"source": "TNF", "target": "TP53", "combined_score": 0.5},
    ]
    # Wire nodes with community assignments via stage_6 node data
    nodes = [
        {"data": {"id": "AKT1", "label": "AKT1", "community_id": 0}},
        {"data": {"id": "TNF", "label": "TNF", "community_id": 0}},
        {"data": {"id": "TP53", "label": "TP53", "community_id": 0}},
    ]
    run_obj = MagicMock(spec=AnalysisRun)
    run_obj.analysis_id = "test-analysis-id"
    run_obj.parameters = {}
    run_obj.stage_results = {"stage_6": {"edges": edges, "nodes": nodes}}
    config = PipelineConfig()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    session.exec = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.commit = AsyncMock()

    result = asyncio.run(stage7_hub_genes.run(run_obj, config, session))

    assert "community_hubs" in result
    assert isinstance(result["community_hubs"], dict)
