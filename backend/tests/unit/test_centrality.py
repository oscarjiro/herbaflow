import networkx as nx
from analysis.stages.stage7_hub_genes import compute_hub_genes


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
