"""Tests for the shared-contract loader and the contract's JSON-Schema validity."""

from jsonschema import Draft202012Validator

from app import contracts


def test_contract_is_valid_json_schema():
    # check_schema raises if the document is not a valid Draft 2020-12 schema.
    Draft202012Validator.check_schema(contracts.raw())


def test_modes():
    assert contracts.modes() == ("auto", "guided")


def test_stage_states():
    assert contracts.stage_states() == ("computed", "user_provided", "not_applicable")


def test_run_status_flat():
    assert contracts.run_status_flat() == ("pending", "complete", "failed")


def test_stage_phases():
    assert contracts.stage_phases() == (
        "starting",
        "running",
        "awaiting_approval",
        "complete",
    )


def test_pipeline_parameters_groups():
    params = contracts.pipeline_parameters()
    assert set(params) == {
        "adme",
        "target",
        "disease_targets",
        "ppi",
        "hub_genes",
        "enrichment",
    }
    assert params["disease_targets"]["properties"]["min_score"]["minimum"] == 0
    assert params["disease_targets"]["properties"]["min_score"]["maximum"] == 1


def test_max_plants_is_twenty() -> None:
    from app import contracts

    assert contracts.max_plants() == 20


def test_default_mode_is_guided() -> None:
    from app import contracts

    assert contracts.default_mode() == "guided"
    assert contracts.default_mode() in contracts.modes()


def test_adme_defaults_match_methodology_lock() -> None:
    from app import contracts

    d = contracts.adme_defaults()
    assert d == {
        "max_mw": 500,
        "max_logp": 5,
        "max_hbd": 5,
        "max_hba": 10,
        "max_tpsa": 140,
        "max_rotatable_bonds": 10,
        "apply_veber": True,
        "np_exception_threshold": 0,
        "apply_np_exception": True,
        "max_violations": 1,
        "skip_adme": False,
    }


def test_input_mode_accessors() -> None:
    assert contracts.plant_input_modes() == ("selection", "manual_compounds", "manual_targets")
    assert contracts.disease_input_modes() == ("selection", "manual_disease_targets")
    assert contracts.default_plant_input_mode() == "selection"
    assert contracts.default_disease_input_mode() == "selection"


def test_apply_adme_to_manual_is_removed() -> None:
    from app import contracts

    assert "apply_adme_to_manual" not in contracts.pipeline_parameters()["adme"]["properties"]


def test_adme_params_carry_description_bounds_and_recommendation() -> None:
    from app import contracts

    b = contracts.pipeline_param_bounds("adme")
    assert all(spec.get("description") for spec in b.values())
    assert (b["max_mw"]["exclusiveMinimum"], b["max_mw"]["maximum"]) == (0, 2000)
    assert (b["max_mw"]["recommended_min"], b["max_mw"]["recommended_max"]) == (350, 600)
    assert (b["max_violations"]["minimum"], b["max_violations"]["maximum"]) == (0, 4)
    npt = b["np_exception_threshold"]
    assert (npt["minimum"], npt["maximum"]) == (-5, 5)
    assert "minimum" not in b["skip_adme"] and "maximum" not in b["skip_adme"]


def test_stage_sources_computed():
    srcs = contracts.stage_sources(3)
    names = [s["name"] for s in srcs]
    assert names == ["ChEMBL", "PubChem BioAssay", "UniProt"]


def test_stage_source_labels_use_public_tool_names():
    assert [s["name"] for s in contracts.stage_sources(1)] == [
        "KNApSAcK",
        "PubChem",
    ]
    assert [s["name"] for s in contracts.stage_sources(2)] == [
        "RDKit (MW/logP/HBD/HBA/TPSA/RotB/NP-score/PAINS)"
    ]
    assert [s["name"] for s in contracts.stage_sources(7)] == [
        "NetworkX",
    ]
    assert [s["name"] for s in contracts.stage_sources(8)] == ["g:Profiler"]


def test_stage_sources_user_provided_overrides():
    srcs = contracts.stage_sources(3, user_provided=True)
    assert len(srcs) == 1
    assert srcs[0]["name"] == "UniProt (manual target resolution)"


def test_stage_sources_user_provided_falls_back_to_computed():
    # Stage 5 has no user_provided override -> computed list.
    assert contracts.stage_sources(5, user_provided=True) == contracts.stage_sources(5)


def test_stage_sources_carry_name_and_url():
    srcs = contracts.stage_sources(3, user_provided=False)
    assert {"name": "ChEMBL", "url": "https://www.ebi.ac.uk/chembl/"} in srcs
    # pseudo-source (set-intersection text) has no page
    s5 = contracts.stage_sources(5, user_provided=False)
    assert all(s["url"] is None or s["url"].startswith("http") for s in s5)


def test_stage_sources_user_provided_unchanged_shape():
    up = contracts.stage_sources(1, user_provided=True)
    assert up[0]["name"].startswith("PubChem")


def test_adme_param_has_unit():
    assert contracts.pipeline_param_bounds("adme")["max_mw"].get("unit") == "Da"
