from unittest.mock import AsyncMock, MagicMock, patch
from analysis.stages import stage8_enrichment
from analysis.models import PipelineConfig
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
        p_value=fdr,
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

    mock_enrich.assert_called_once_with(
        gene_symbols=["EGFR"],
        sources=["GO:BP", "KEGG"],
        fdr_threshold=0.01,
    )
