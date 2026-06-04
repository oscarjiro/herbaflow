from unittest.mock import AsyncMock, MagicMock, patch

from analysis.models import PipelineConfig
from analysis.stages import stage6_ppi
from app.models.analysis import AnalysisRun
from integrations.stringdb import PpiEdgeData


def make_run(overlap=None):
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {}
    run.stage_results = {"stage_5": {"overlap": overlap or []}}
    return run


async def test_stage6_empty_overlap_returns_zero_counts():
    run = make_run(overlap=[])
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage6_ppi.run(run, config, session)

    assert result["node_count"] == 0
    assert result["edge_count"] == 0
    assert result["nodes"] == []
    assert result["edges"] == []


async def test_stage6_builds_network_from_string_edges():
    run = make_run(overlap=["AKT1", "TNF", "TP53"])
    config = PipelineConfig()
    session = AsyncMock()

    fake_edges = [
        PpiEdgeData(
            gene_a="AKT1", gene_b="TNF",
            combined_score=0.7, experimental_score=0.5,
            textmining_score=0.3, coexpression_score=0.2,
        ),
        PpiEdgeData(
            gene_a="TNF", gene_b="TP53",
            combined_score=0.6, experimental_score=0.4,
            textmining_score=0.2, coexpression_score=0.1,
        ),
    ]

    with patch("analysis.stages.stage6_ppi.get_ppi_network", return_value=fake_edges):
        result = await stage6_ppi.run(run, config, session)

    assert result["node_count"] == 3
    assert result["edge_count"] == 2
    node_ids = [n["data"]["id"] for n in result["nodes"]]
    assert "AKT1" in node_ids
    assert "TNF" in node_ids
    assert "TP53" in node_ids


async def test_stage6_returns_cytoscape_format():
    run = make_run(overlap=["EGFR", "BRCA1"])
    config = PipelineConfig()
    session = AsyncMock()

    fake_edges = [
        PpiEdgeData(
            gene_a="EGFR", gene_b="BRCA1",
            combined_score=0.8, experimental_score=0.6,
            textmining_score=0.4, coexpression_score=0.3,
        ),
    ]

    with patch("analysis.stages.stage6_ppi.get_ppi_network", return_value=fake_edges):
        result = await stage6_ppi.run(run, config, session)

    # Impl returns nodes/edges in Cytoscape.js element format (no wrapper key)
    assert "nodes" in result
    assert "edges" in result
    assert result["edges"][0]["data"]["source"] in {"EGFR", "BRCA1"}
    assert "weight" in result["edges"][0]["data"]
    assert result["nodes"][0]["data"]["id"] in {"EGFR", "BRCA1"}


def test_leiden_assigns_community_to_every_node():
    """Every node in PPI result must have a community_id field."""
    import networkx as nx
    from analysis.stages.stage6_ppi import detect_communities

    G = nx.Graph()
    G.add_edges_from([('TP53', 'MDM2'), ('MDM2', 'MDM4'), ('BRCA1', 'BARD1'), ('BARD1', 'BRCA2')])
    communities = detect_communities(G, resolution=1.0)

    # Every node must appear
    assert set(communities.keys()) == set(G.nodes())
    # Community IDs must be non-negative integers
    assert all(isinstance(v, int) and v >= 0 for v in communities.values())
    # At least 1 community must exist
    assert len(set(communities.values())) >= 1


def test_leiden_deterministic_with_seed():
    """Same graph + same seed must produce identical community assignments."""
    import networkx as nx
    from analysis.stages.stage6_ppi import detect_communities

    G = nx.Graph()
    G.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'E'), ('E', 'A'), ('A', 'C')])
    result1 = detect_communities(G, resolution=1.0, seed=42)
    result2 = detect_communities(G, resolution=1.0, seed=42)
    assert result1 == result2


async def test_stage6_nodes_have_community_id():
    """Each node in the stage 6 result must have community_id in its data."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from analysis.models import PipelineConfig
    from analysis.stages import stage6_ppi
    from app.models.analysis import AnalysisRun
    from integrations.stringdb import PpiEdgeData

    run = MagicMock(spec=AnalysisRun)
    run.parameters = {}
    run.stage_results = {"stage_5": {"overlap": ["AKT1", "TNF", "TP53"]}}
    config = PipelineConfig()
    session = AsyncMock()

    fake_edges = [
        PpiEdgeData(gene_a="AKT1", gene_b="TNF", combined_score=0.7,
                    experimental_score=0.5, textmining_score=0.3, coexpression_score=0.2),
        PpiEdgeData(gene_a="TNF", gene_b="TP53", combined_score=0.6,
                    experimental_score=0.4, textmining_score=0.2, coexpression_score=0.1),
    ]

    with patch("analysis.stages.stage6_ppi.get_ppi_network", return_value=fake_edges):
        result = await stage6_ppi.run(run, config, session)

    # Every node must have community_id in its data dict
    for node in result["nodes"]:
        assert "community_id" in node["data"], f"Node {node['data']['id']} missing community_id"
        assert isinstance(node["data"]["community_id"], int)


async def test_stage6_includes_isolated_overlap_genes():
    """Overlap genes with no STRING edge must still appear as degree-0 nodes."""
    run = make_run(overlap=["AKT1", "TNF", "LONELY"])
    config = PipelineConfig()
    session = AsyncMock()

    fake_edges = [
        PpiEdgeData(gene_a="AKT1", gene_b="TNF", combined_score=0.7,
                    experimental_score=0.5, textmining_score=0.3, coexpression_score=0.2),
    ]

    with patch("analysis.stages.stage6_ppi.get_ppi_network", return_value=fake_edges):
        result = await stage6_ppi.run(run, config, session)

    node_ids = [n["data"]["id"] for n in result["nodes"]]
    assert "LONELY" in node_ids
    assert result["node_count"] == 3
    lonely = next(n for n in result["nodes"] if n["data"]["id"] == "LONELY")
    assert lonely["data"]["degree"] == 0
    assert lonely["data"]["type"] == "overlap"


async def test_stage6_isolated_genes_get_singleton_community_not_counted():
    """Isolated genes get their own community id; singletons excluded from n_communities."""
    config = PipelineConfig()
    session = AsyncMock()
    fake_edges = [
        PpiEdgeData(gene_a="AKT1", gene_b="TNF", combined_score=0.7,
                    experimental_score=0.5, textmining_score=0.3, coexpression_score=0.2),
        PpiEdgeData(gene_a="TNF", gene_b="MDM2", combined_score=0.6,
                    experimental_score=0.4, textmining_score=0.2, coexpression_score=0.1),
    ]

    base_run = make_run(overlap=["AKT1", "TNF", "MDM2"])
    iso_run = make_run(overlap=["AKT1", "TNF", "MDM2", "LONELY"])

    with patch("analysis.stages.stage6_ppi.get_ppi_network", return_value=fake_edges):
        base = await stage6_ppi.run(base_run, config, session)
    with patch("analysis.stages.stage6_ppi.get_ppi_network", return_value=fake_edges):
        iso = await stage6_ppi.run(iso_run, config, session)

    # LONELY's community id differs from every connected node's community id
    connected_ids = {n["data"]["community_id"] for n in iso["nodes"]
                     if n["data"]["id"] in {"AKT1", "TNF", "MDM2"}}
    lonely = next(n for n in iso["nodes"] if n["data"]["id"] == "LONELY")
    assert lonely["data"]["community_id"] not in connected_ids

    # Singleton does not inflate the count, and connected grouping is unchanged
    assert iso["n_communities"] == base["n_communities"]

    def grouping(res):
        from collections import defaultdict
        groups = defaultdict(set)
        for n in res["nodes"]:
            if n["data"]["id"] in {"AKT1", "TNF", "MDM2"}:
                groups[n["data"]["community_id"]].add(n["data"]["id"])
        return sorted(tuple(sorted(s)) for s in groups.values())

    assert grouping(iso) == grouping(base)


async def test_stage6_propagates_string_outage():
    """STRING-DB ServiceUnavailableError must bubble out of stage 6 run()."""
    from integrations._retry import ServiceUnavailableError

    run = make_run(overlap=["TP53", "EGFR"])
    config = PipelineConfig()
    session = AsyncMock()

    with patch(
        "analysis.stages.stage6_ppi.get_ppi_network",
        side_effect=ServiceUnavailableError("STRING-DB", 503),
    ):
        import pytest
        with pytest.raises(ServiceUnavailableError):
            await stage6_ppi.run(run, config, session)
