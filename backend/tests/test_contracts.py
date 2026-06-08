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
