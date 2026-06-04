from unittest.mock import AsyncMock, MagicMock, patch

from analysis.models import PipelineConfig
from analysis.stages import stage8_enrichment
from app.models.analysis import AnalysisRun
from integrations.gprofiler import EnrichmentResult


def make_run(ranked=None):
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {}
    run.stage_results = {"stage_7": {"ranked": ranked or []}}
    return run


def make_result(source: str, term_id: str, term_name: str, fdr: float = 0.01) -> EnrichmentResult:
    return EnrichmentResult(
        source=source,
        term_id=term_id,
        term_name=term_name,
        fdr=fdr,
        intersection_size=2,
        term_size=100,
        query_size=5,
        genes=["AKT1", "TNF"],
    )


async def test_stage8_empty_hub_genes_early_return():
    run = make_run(ranked=[])
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage8_enrichment.run(run, config, session)

    assert result["total_significant"] == 0
    assert result["go_bp"] == []
    assert result["go_mf"] == []
    assert result["go_cc"] == []
    assert result["kegg"] == []


async def test_stage8_groups_results_by_source():
    run = make_run(ranked=[{"gene_symbol": "AKT1"}, {"gene_symbol": "TNF"}])
    config = PipelineConfig()
    session = AsyncMock()

    fake_results = [
        make_result("GO:BP", "GO:0006915", "apoptotic process", fdr=0.001),
        make_result("KEGG", "hsa04151", "PI3K-Akt signaling", fdr=0.005),
        make_result("GO:MF", "GO:0004672", "protein kinase activity", fdr=0.02),
    ]

    with patch("analysis.stages.stage8_enrichment.run_enrichment", return_value=fake_results):
        result = await stage8_enrichment.run(run, config, session)

    assert result["total_significant"] == 3
    assert len(result["go_bp"]) == 1
    assert result["go_bp"][0]["term_id"] == "GO:0006915"
    assert len(result["kegg"]) == 1
    assert result["kegg"][0]["term_id"] == "hsa04151"
    assert len(result["go_mf"]) == 1
    assert result["hub_genes_queried"] == ["AKT1", "TNF"]


async def test_stage8_sorts_by_fdr_within_source():
    run = make_run(ranked=[{"gene_symbol": "TP53"}])
    config = PipelineConfig()
    session = AsyncMock()

    fake_results = [
        make_result("GO:BP", "GO:0009999", "high fdr term", fdr=0.04),
        make_result("GO:BP", "GO:0001111", "low fdr term", fdr=0.001),
        make_result("GO:BP", "GO:0002222", "mid fdr term", fdr=0.01),
    ]

    with patch("analysis.stages.stage8_enrichment.run_enrichment", return_value=fake_results):
        result = await stage8_enrichment.run(run, config, session)

    fdrs = [r["fdr"] for r in result["go_bp"]]
    assert fdrs == sorted(fdrs)
    assert result["go_bp"][0]["term_id"] == "GO:0001111"


async def test_stage8_passes_config_params_to_enrichment():
    run = make_run(ranked=[{"gene_symbol": "EGFR"}])
    config = PipelineConfig()
    config.enrichment.fdr_threshold = 0.01
    config.enrichment.sources = ["GO:BP", "KEGG"]
    session = AsyncMock()

    with patch(
        "analysis.stages.stage8_enrichment.run_enrichment", return_value=[]
    ) as mock_enrich:
        await stage8_enrichment.run(run, config, session)

    # run_enrichment called twice (legacy overall + global); per-community skipped
    # because single-gene communities are below the minimum-gene threshold
    # Both calls use the same config params — verify the first call
    assert mock_enrich.call_count == 2
    first_call_kwargs = mock_enrich.call_args_list[0].kwargs
    assert first_call_kwargs["gene_symbols"] == ["EGFR"]
    assert first_call_kwargs["sources"] == ["GO:BP", "KEGG"]
    assert first_call_kwargs["fdr_threshold"] == 0.01
    assert first_call_kwargs["background"] is None


async def test_stage8_includes_global_enrichment():
    """Stage 8 result must include global_enrichment with all hub genes combined."""
    run = make_run(ranked=[
        {"gene_symbol": "AKT1", "community_id": 0},
        {"gene_symbol": "TNF", "community_id": 0},
        {"gene_symbol": "TP53", "community_id": 1},
        {"gene_symbol": "EGFR", "community_id": 1},
        {"gene_symbol": "VEGFA", "community_id": 1},
    ])
    config = PipelineConfig()
    session = AsyncMock()

    fake_results = [
        make_result("GO:BP", "GO:0006915", "apoptotic process", fdr=0.001),
        make_result("KEGG", "hsa04151", "PI3K-Akt signaling", fdr=0.005),
    ]

    with patch("analysis.stages.stage8_enrichment.run_enrichment", return_value=fake_results):
        result = await stage8_enrichment.run(run, config, session)

    assert "global_enrichment" in result
    ge = result["global_enrichment"]
    assert isinstance(ge["go_bp"], list)
    assert isinstance(ge["go_mf"], list)
    assert isinstance(ge["go_cc"], list)
    assert isinstance(ge["kegg"], list)
    assert isinstance(ge["hub_genes_queried"], list)
    assert set(ge["hub_genes_queried"]) == {"AKT1", "TNF", "TP53", "EGFR", "VEGFA"}


async def test_stage8_global_enrichment_empty_when_no_hub_genes():
    """global_enrichment must be present in the early-return path too."""
    run = make_run(ranked=[])
    config = PipelineConfig()
    session = AsyncMock()

    result = await stage8_enrichment.run(run, config, session)

    assert "global_enrichment" in result
    ge = result["global_enrichment"]
    assert ge["go_bp"] == []
    assert ge["go_mf"] == []
    assert ge["go_cc"] == []
    assert ge["kegg"] == []
    assert ge["hub_genes_queried"] == []


async def test_stage8_global_enrichment_deduplicated_genes():
    """hub_genes_queried in global_enrichment should have no duplicates."""
    # Same gene in two communities (edge case: shouldn't happen in practice but guard it)
    run = make_run(ranked=[
        {"gene_symbol": "AKT1", "community_id": 0},
        {"gene_symbol": "TNF", "community_id": 0},
        {"gene_symbol": "AKT1", "community_id": 1},  # duplicate
    ])
    config = PipelineConfig()
    session = AsyncMock()

    with patch("analysis.stages.stage8_enrichment.run_enrichment", return_value=[]):
        result = await stage8_enrichment.run(run, config, session)

    ge = result["global_enrichment"]
    assert len(ge["hub_genes_queried"]) == len(set(ge["hub_genes_queried"]))


import pytest
from integrations._retry import ServiceUnavailableError


@pytest.mark.asyncio
async def test_stage8_degrades_when_gprofiler_unavailable():
    run = type("R", (), {"stage_results": {
        "stage_7": {"ranked": [{"gene_symbol": "TP53", "community_id": 0}]},
        "stage_3": {"target_gene_symbols": ["TP53", "EGFR"]},
    }})()
    config = PipelineConfig.from_dict({})
    with patch.object(
        stage8_enrichment, "run_enrichment",
        side_effect=ServiceUnavailableError("g:Profiler", 503),
    ):
        result = await stage8_enrichment.run(run, config, session=None)
    assert result["degraded"] is True
    assert result["warning"]["provider"] == "g:Profiler"
    assert result["total_significant"] == 0
    assert result["go_bp"] == []


def test_group_by_source_omits_p_value():
    from analysis.stages.stage8_enrichment import _group_by_source
    from integrations.gprofiler import EnrichmentResult
    r = EnrichmentResult(
        source="GO:BP", term_id="GO:1", term_name="x",
        fdr=0.01, intersection_size=2, term_size=10, query_size=5, genes=["TP53"],
    )
    grouped = _group_by_source([r])
    row = grouped["GO:BP"][0]
    assert "p_value" not in row
    assert row["fdr"] == 0.01
