from unittest.mock import AsyncMock, MagicMock, patch
from analysis.stages import stage3_targets
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from integrations.chembl import ChemblTarget
from integrations.pubchem_bioassay import PubChemTarget


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


def make_fake_compound(
    compound_id: str,
    chembl_id: str | None,
    inchi_key: str | None = None,
    canonical_name: str = "Test Compound",
    smiles: str | None = "C1CCCCC1",
):
    m = MagicMock()
    m.compound_id = compound_id
    m.chembl_id = chembl_id
    m.inchi_key = inchi_key
    m.canonical_name = canonical_name
    m.smiles = smiles
    return m


def _mock_httpx_client():
    """Return a mock httpx.AsyncClient usable as an async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=MagicMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


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


async def test_stage3_pubchem_fallback_covers_uncovered_compound():
    """
    Compounds with 0 ChEMBL targets are queried via PubChem BioAssay by InChIKey.
    A compound with no chembl_id but a valid inchi_key should be covered if
    PubChem returns an active human target.
    """
    run = make_run(all_active_compound_ids=["c1"])
    config = PipelineConfig()
    session = make_session()
    # No ChEMBL ID; has InChIKey → triggers PubChem fallback
    fake_compound = make_fake_compound(
        "c1", chembl_id=None, inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    )

    fake_pubchem_target = PubChemTarget(
        uniprot_accession="P31749",
        gene_symbol="AKT1",
        protein_name="RAC-alpha serine/threonine-protein kinase",
    )

    with patch(
        "analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids",
        return_value=[fake_compound],
    ):
        with patch(
            "analysis.stages.stage3_targets.get_targets_for_compounds",
            return_value={},
        ):
            with patch(
                "analysis.stages.stage3_targets.get_targets_by_inchikey",
                new=AsyncMock(return_value=[fake_pubchem_target]),
            ):
                with patch(
                    "analysis.stages.stage3_targets.httpx.AsyncClient",
                    return_value=_mock_httpx_client(),
                ):
                    result = await stage3_targets.run(run, config, session)

    assert result["covered"] == 1
    assert result["coverage_pct"] == 100.0
    assert "AKT1" in result["target_gene_symbols"]
    assert result["target_count"] == 1


async def test_stage3_pubchem_not_called_when_chembl_covers_all():
    """PubChem fallback is skipped if all compounds are covered by ChEMBL."""
    run = make_run(all_active_compound_ids=["c1"])
    config = PipelineConfig()
    session = make_session()
    fake_compound = make_fake_compound("c1", chembl_id="CHEMBL999", inchi_key="SOMEKEY-XXX")

    fake_target = ChemblTarget(
        chembl_id="CHEMBL_TGT_1",
        gene_symbol="EGFR",
        uniprot_accession="P00533",
        organism="Homo sapiens",
        pchembl_value=8.0,
    )

    pubchem_mock = AsyncMock(return_value=[])

    with patch(
        "analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids",
        return_value=[fake_compound],
    ):
        with patch(
            "analysis.stages.stage3_targets.get_targets_for_compounds",
            return_value={"CHEMBL999": [fake_target]},
        ):
            with patch(
                "analysis.stages.stage3_targets.get_targets_by_inchikey",
                new=pubchem_mock,
            ):
                result = await stage3_targets.run(run, config, session)

    # PubChem should never have been called
    pubchem_mock.assert_not_called()
    assert result["covered"] == 1
    assert "EGFR" in result["target_gene_symbols"]


@patch("analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids")
@patch("analysis.stages.stage3_targets.get_targets_for_compounds")
@patch("analysis.stages.stage3_targets.get_targets_by_inchikey")
async def test_stage3_uncovered_compounds_in_output(
    mock_pubchem, mock_chembl, mock_get_compounds
):
    """Compounds with 0 targets appear in uncovered_compounds with name and smiles."""
    covered_cid = "cid-covered"
    uncovered_cid = "cid-uncovered"

    mock_get_compounds.return_value = [
        make_fake_compound(covered_cid, "CHEMBL1", canonical_name="Quercetin", smiles="OC1=CC=CC=C1"),
        make_fake_compound(uncovered_cid, None, inchi_key="ABCDEF", canonical_name="Kaempferol", smiles="CC1=CC=CC=C1"),
    ]

    mock_chembl.return_value = {
        "CHEMBL1": [ChemblTarget(chembl_id="CHEMBL_TGT_1", gene_symbol="TP53", uniprot_accession="P04637", organism="Homo sapiens", pchembl_value=6.0)]
    }
    mock_pubchem.return_value = []  # PubChem returns nothing for uncovered_cid

    run = make_run(all_active_compound_ids=[covered_cid, uncovered_cid])
    config = PipelineConfig()
    session = make_session()

    with patch("httpx.AsyncClient", return_value=_mock_httpx_client()):
        result = await stage3_targets.run(run, config, session)

    assert "uncovered_compounds" in result
    uncovered = result["uncovered_compounds"]
    assert len(uncovered) == 1
    assert uncovered[0]["compound_id"] == uncovered_cid
    assert uncovered[0]["canonical_name"] == "Kaempferol"
    assert uncovered[0]["smiles"] == "CC1=CC=CC=C1"
