from unittest.mock import AsyncMock, MagicMock, patch
from analysis.stages import stage3_targets
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from integrations.chembl import ChemblTarget


def make_run(all_active_compound_ids=None):
    run = MagicMock(spec=AnalysisRun)
    run.parameters = {}
    run.stage_results = {
        "stage_2": {"all_active_compound_ids": all_active_compound_ids or []}
    }
    return run


def make_session():
    session = AsyncMock()
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = None
    session.exec = AsyncMock(return_value=mock_exec_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def make_fake_compound(compound_id: str, chembl_id: str | None):
    m = MagicMock()
    m.compound_id = compound_id
    m.chembl_id = chembl_id
    return m


async def test_stage3_empty_compound_ids_early_return():
    run = make_run(all_active_compound_ids=[])
    config = PipelineConfig()
    session = make_session()

    result = await stage3_targets.run(run, config, session)

    assert result["covered"] == 0
    assert result["coverage_pct"] == 0.0
    assert result["targets"] == []


async def test_stage3_compound_without_chembl_id_not_covered():
    run = make_run(all_active_compound_ids=["c1"])
    config = PipelineConfig()
    session = make_session()
    fake_compound = make_fake_compound("c1", chembl_id=None)

    with patch(
        "analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids",
        return_value=[fake_compound],
    ):
        with patch(
            "analysis.stages.stage3_targets.get_targets_for_compounds",
            return_value={},
        ):
            result = await stage3_targets.run(run, config, session)

    assert result["covered"] == 0
    assert result["coverage_pct"] == 0.0


async def test_stage3_maps_chembl_targets_correctly():
    run = make_run(all_active_compound_ids=["c1"])
    config = PipelineConfig()
    session = make_session()
    fake_compound = make_fake_compound("c1", chembl_id="CHEMBL123")

    fake_target = ChemblTarget(
        chembl_id="CHEMBL_TGT_1",
        gene_symbol="AKT1",
        uniprot_accession="P31749",
        organism="Homo sapiens",
        pchembl_value=6.5,
    )

    with patch(
        "analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids",
        return_value=[fake_compound],
    ):
        with patch(
            "analysis.stages.stage3_targets.get_targets_for_compounds",
            return_value={"CHEMBL123": [fake_target]},
        ):
            result = await stage3_targets.run(run, config, session)

    assert result["covered"] == 1
    assert "AKT1" in result["target_gene_symbols"]
    assert result["coverage_pct"] == 100.0
    assert result["target_count"] == 1


async def test_stage3_multiple_compounds_same_target():
    run = make_run(all_active_compound_ids=["c1", "c2"])
    config = PipelineConfig()
    session = make_session()

    fake_c1 = make_fake_compound("c1", chembl_id="CHEMBL1")
    fake_c2 = make_fake_compound("c2", chembl_id="CHEMBL2")

    shared_target = ChemblTarget(
        chembl_id="CHEMBL_TGT_X",
        gene_symbol="TP53",
        uniprot_accession="P04637",
        organism="Homo sapiens",
        pchembl_value=7.0,
    )

    with patch(
        "analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids",
        return_value=[fake_c1, fake_c2],
    ):
        with patch(
            "analysis.stages.stage3_targets.get_targets_for_compounds",
            return_value={"CHEMBL1": [shared_target], "CHEMBL2": [shared_target]},
        ):
            result = await stage3_targets.run(run, config, session)

    assert result["target_count"] == 1
    assert "TP53" in result["target_gene_symbols"]
    assert result["covered"] == 2
