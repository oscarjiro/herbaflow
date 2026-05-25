"""Unit tests for Stage 4 multi-disease target tagging."""
from unittest.mock import AsyncMock, MagicMock, patch
from analysis.stages import stage4_disease_targets
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun


def make_run(disease_ids=None):
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {"_disease_ids": disease_ids or []}
    run.stage_results = {}
    return run


def make_fake_disease(disease_id: str, disease_name: str, ontology_id: str = "EFO_0000400"):
    m = MagicMock()
    m.disease_id = disease_id
    m.disease_name = disease_name
    m.ontology_id = ontology_id
    return m


def make_fake_target(gene_symbol: str, uniprot: str = "P00000"):
    m = MagicMock()
    m.gene_symbol = gene_symbol
    m.uniprot_accession = uniprot
    return m


async def test_gene_in_multiple_diseases_has_both_in_diseases_list():
    """A gene shared across two diseases must have both entries in its `diseases` list."""
    run = make_run(disease_ids=["dis_1", "dis_2"])
    config = PipelineConfig()
    session = AsyncMock()

    fake_disease1 = make_fake_disease("dis_1", "Diabetes")
    fake_disease2 = make_fake_disease("dis_2", "Obesity")
    shared_target = make_fake_target("TP53")

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        side_effect=[fake_disease1, fake_disease2],
    ):
        with patch(
            "analysis.stages.stage4_disease_targets.disease_repo.get_targets_for_disease",
            side_effect=[[(shared_target, 0.8)], [(shared_target, 0.6)]],
        ):
            result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_target_count"] == 1
    target = result["targets"][0]
    assert target["gene_symbol"] == "TP53"

    # Both diseases must appear in the diseases list
    disease_ids_in_list = {d["disease_id"] for d in target["diseases"]}
    assert "dis_1" in disease_ids_in_list
    assert "dis_2" in disease_ids_in_list
    assert len(target["diseases"]) == 2


async def test_highest_score_wins_for_association_score():
    """When the same gene appears in two diseases, association_score = max of all scores."""
    run = make_run(disease_ids=["dis_1", "dis_2"])
    config = PipelineConfig()
    session = AsyncMock()

    fake_disease1 = make_fake_disease("dis_1", "Diabetes")
    fake_disease2 = make_fake_disease("dis_2", "Obesity")
    target = make_fake_target("AKT1")

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        side_effect=[fake_disease1, fake_disease2],
    ):
        with patch(
            "analysis.stages.stage4_disease_targets.disease_repo.get_targets_for_disease",
            side_effect=[[(target, 0.5)], [(target, 0.9)]],
        ):
            result = await stage4_disease_targets.run(run, config, session)

    assert result["targets"][0]["association_score"] == 0.9


async def test_disease_gene_symbols_by_disease_populated_correctly():
    """disease_gene_symbols_by_disease maps each disease_id to its gene list."""
    run = make_run(disease_ids=["dis_1", "dis_2"])
    config = PipelineConfig()
    session = AsyncMock()

    fake_disease1 = make_fake_disease("dis_1", "Diabetes")
    fake_disease2 = make_fake_disease("dis_2", "Obesity")
    target1 = make_fake_target("BRCA1")
    target2 = make_fake_target("EGFR")
    # target1 is shared
    target1_copy = make_fake_target("BRCA1")

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        side_effect=[fake_disease1, fake_disease2],
    ):
        with patch(
            "analysis.stages.stage4_disease_targets.disease_repo.get_targets_for_disease",
            side_effect=[
                [(target1, 0.7), (target2, 0.6)],
                [(target1_copy, 0.8)],
            ],
        ):
            result = await stage4_disease_targets.run(run, config, session)

    by_disease = result["disease_gene_symbols_by_disease"]
    assert "dis_1" in by_disease
    assert "dis_2" in by_disease
    assert set(by_disease["dis_1"]) == {"BRCA1", "EGFR"}
    assert set(by_disease["dis_2"]) == {"BRCA1"}


async def test_unique_genes_from_different_diseases_are_all_included():
    """Genes unique to each disease both appear in the combined target list."""
    run = make_run(disease_ids=["dis_1", "dis_2"])
    config = PipelineConfig()
    session = AsyncMock()

    fake_disease1 = make_fake_disease("dis_1", "Diabetes")
    fake_disease2 = make_fake_disease("dis_2", "Cancer")
    target1 = make_fake_target("BRCA1")
    target2 = make_fake_target("EGFR")

    with patch(
        "analysis.stages.stage4_disease_targets.disease_repo.get_disease_by_id",
        side_effect=[fake_disease1, fake_disease2],
    ):
        with patch(
            "analysis.stages.stage4_disease_targets.disease_repo.get_targets_for_disease",
            side_effect=[[(target1, 0.7)], [(target2, 0.8)]],
        ):
            result = await stage4_disease_targets.run(run, config, session)

    assert result["disease_target_count"] == 2
    gene_symbols = result["disease_gene_symbols"]
    assert "BRCA1" in gene_symbols
    assert "EGFR" in gene_symbols

    # Each target has exactly one disease entry
    brca = next(t for t in result["targets"] if t["gene_symbol"] == "BRCA1")
    assert len(brca["diseases"]) == 1
    assert brca["diseases"][0]["disease_id"] == "dis_1"
