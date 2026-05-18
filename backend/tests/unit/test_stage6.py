from unittest.mock import AsyncMock, MagicMock, patch
from analysis.stages import stage6_ppi
from analysis.models import PipelineConfig
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
    node_ids = [n["id"] for n in result["nodes"]]
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

    assert "cytoscape" in result
    cyto = result["cytoscape"]["elements"]
    assert "nodes" in cyto
    assert "edges" in cyto
    assert cyto["edges"][0]["data"]["source"] in {"EGFR", "BRCA1"}
    assert "weight" in cyto["edges"][0]["data"]
