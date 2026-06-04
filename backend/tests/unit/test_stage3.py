import uuid
import pytest
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
    assert not any(u["compound_id"] == covered_cid for u in uncovered)


async def test_coverage_pct_nonzero_when_targets_found():
    """Coverage % must be > 0 when targets are found, even if compound IDs arrive
    as uuid.UUID objects from Stage 2 instead of plain strings.

    Regression guard: a prior bug caused the set intersection
        all_covered & set(compound_ids)
    to return empty when compound_ids contained UUID objects (not strings),
    because all_covered is built from string compound IDs stored in the DB.
    Passing UUID objects here confirms stage3 now produces coverage_pct > 0.
    """
    # Simulate the pre-fix bug scenario: Stage 2 emits UUID objects, not strings.
    cid1 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    cid2 = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    # DB compounds are keyed by their string representation (as stored in PostgreSQL)
    cid1_str = str(cid1)
    cid2_str = str(cid2)

    run = make_run(all_active_compound_ids=[cid1, cid2])
    config = PipelineConfig()
    session = make_session()

    fake_c1 = make_fake_compound(cid1_str, chembl_id="CHEMBL_A")
    fake_c2 = make_fake_compound(cid2_str, chembl_id="CHEMBL_B")

    fake_target_c1 = ChemblTarget(
        chembl_id="CHEMBL_TGT_1",
        gene_symbol="TP53",
        uniprot_accession="P04637",
        organism="Homo sapiens",
        pchembl_value=6.0,
    )
    fake_target_c2 = ChemblTarget(
        chembl_id="CHEMBL_TGT_2",
        gene_symbol="EGFR",
        uniprot_accession="P00533",
        organism="Homo sapiens",
        pchembl_value=7.0,
    )

    with patch(
        "analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids",
        return_value=[fake_c1, fake_c2],
    ):
        with patch(
            "analysis.stages.stage3_targets.get_targets_for_compounds",
            return_value={"CHEMBL_A": [fake_target_c1], "CHEMBL_B": [fake_target_c2]},
        ):
            result = await stage3_targets.run(run, config, session)

    assert result["coverage_pct"] == 100.0, (
        f"coverage_pct was {result['coverage_pct']} — UUID objects in "
        "all_active_compound_ids likely broke the set intersection"
    )


# ---------------------------------------------------------------------------
# Regression: stage3 output key is coverage_pct not coverage_percent
# ---------------------------------------------------------------------------

async def test_stage3_output_uses_coverage_pct_field():
    """Stage 3 result dict must use key 'coverage_pct', not 'coverage_percent'.

    Regression guard: an earlier implementation used 'coverage_percent' which
    broke the frontend Stage 3 table and downstream stage checks.
    """
    run = make_run(all_active_compound_ids=["c1"])
    config = PipelineConfig()
    session = make_session()
    fake_compound = make_fake_compound("c1", chembl_id="CHEMBL_REG")

    fake_target = ChemblTarget(
        chembl_id="CHEMBL_TGT_REG",
        gene_symbol="EGFR",
        uniprot_accession="P00533",
        organism="Homo sapiens",
        pchembl_value=6.0,
    )

    with patch(
        "analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids",
        return_value=[fake_compound],
    ):
        with patch(
            "analysis.stages.stage3_targets.get_targets_for_compounds",
            return_value={"CHEMBL_REG": [fake_target]},
        ):
            result = await stage3_targets.run(run, config, session)

    # Must have 'coverage_pct', must NOT have 'coverage_percent'
    assert "coverage_pct" in result, (
        f"Stage 3 output missing 'coverage_pct'. Keys found: {list(result.keys())}"
    )
    assert "coverage_percent" not in result, (
        "Stage 3 output must use 'coverage_pct', not the old 'coverage_percent' key"
    )
    assert isinstance(result["coverage_pct"], float)


# ─────────────────────────────────────────────────────────────────────────────
# Provider-outage failure routing: ChEMBL (critical) propagates, PubChem degrades
# ─────────────────────────────────────────────────────────────────────────────
from integrations._retry import ServiceUnavailableError


@pytest.fixture
def pipeline_config():
    return PipelineConfig.from_dict({})


@pytest.fixture
def stage3_run_with_one_chembl_compound():
    # One active compound that ChEMBL can cover (has chembl_id) but that also
    # carries an inchi_key, so it can fall into the PubChem fallback when ChEMBL
    # does not cover it. Stage 3 reads stage_2.all_active_compound_ids then loads
    # compounds via compound_repo.get_compounds_by_ids — tests patch that loader.
    compound_id = "11111111-1111-5111-8111-111111111111"
    return {
        "compound_id": compound_id,
        "canonical_name": "celecoxib",
        "chembl_id": "CHEMBL118",
        "inchi_key": "RZEKVGVHFLEQIL-UHFFFAOYSA-N",
        "smiles": "O=S(=O)(N)c1ccc(cc1)-c1cc(C(F)(F)F)nn1-c1ccc(C)cc1",
        "run": make_run(all_active_compound_ids=[compound_id]),
    }


async def test_stage3_propagates_chembl_outage(
    stage3_run_with_one_chembl_compound, pipeline_config
):
    # ChEMBL down → stage must raise (critical), not swallow.
    fixture = stage3_run_with_one_chembl_compound
    run = fixture["run"]
    session = make_session()
    fake_compound = make_fake_compound(
        fixture["compound_id"],
        chembl_id=fixture["chembl_id"],
        inchi_key=fixture["inchi_key"],
        canonical_name=fixture["canonical_name"],
        smiles=fixture["smiles"],
    )

    with patch(
        "analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids",
        return_value=[fake_compound],
    ):
        with patch.object(
            stage3_targets,
            "get_targets_for_compounds",
            side_effect=ServiceUnavailableError("ChEMBL", 503),
        ):
            with pytest.raises(ServiceUnavailableError):
                await stage3_targets.run(run, pipeline_config, session)


async def test_stage3_degrades_when_pubchem_fallback_unavailable(
    stage3_run_with_one_chembl_compound, pipeline_config
):
    # ChEMBL ok (returns a target for the covered compound), PubChem fallback down
    # for a SEPARATE uncovered compound → keep ChEMBL data + degraded marker.
    fixture = stage3_run_with_one_chembl_compound
    covered_cid = fixture["compound_id"]
    uncovered_cid = "22222222-2222-5222-8222-222222222222"
    run = make_run(all_active_compound_ids=[covered_cid, uncovered_cid])
    session = make_session()

    covered_compound = make_fake_compound(
        covered_cid,
        chembl_id=fixture["chembl_id"],
        inchi_key=fixture["inchi_key"],
        canonical_name=fixture["canonical_name"],
        smiles=fixture["smiles"],
    )
    # No chembl_id but has an inchi_key → routed into the PubChem fallback.
    uncovered_compound = make_fake_compound(
        uncovered_cid, chembl_id=None, inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    )

    chembl_target = ChemblTarget(
        chembl_id="CHEMBL25",
        gene_symbol="PTGS2",
        uniprot_accession="P35354",
        organism="Homo sapiens",
        pchembl_value=7.0,
    )

    with patch(
        "analysis.stages.stage3_targets.compound_repo.get_compounds_by_ids",
        return_value=[covered_compound, uncovered_compound],
    ):
        with patch.object(
            stage3_targets,
            "get_targets_for_compounds",
            new=AsyncMock(return_value={fixture["chembl_id"]: [chembl_target]}),
        ):
            with patch.object(
                stage3_targets,
                "get_targets_by_inchikey",
                side_effect=ServiceUnavailableError("PubChem BioAssay", 503),
            ):
                with patch(
                    "analysis.stages.stage3_targets.httpx.AsyncClient",
                    return_value=_mock_httpx_client(),
                ):
                    result = await stage3_targets.run(run, pipeline_config, session)

    assert result["target_count"] >= 1
    assert result["degraded"] is True
    assert result["warning"]["provider"] == "pubchem_bioassay"
