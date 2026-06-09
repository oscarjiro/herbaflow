from app.services import structure


def test_smiles_resolves_to_inchikey_and_canonical_smiles() -> None:
    res = structure.identity_from_smiles("CCO")  # ethanol
    assert res is not None
    assert res.inchikey == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    assert res.canonical_smiles == "CCO"


def test_invalid_smiles_returns_none() -> None:
    assert structure.identity_from_smiles("not-a-molecule!!") is None


def test_inchikey_format_validator() -> None:
    assert structure.is_inchikey("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
    assert not structure.is_inchikey("CCO")
    assert not structure.is_inchikey("LFQSCWFLJHTTHZ-UHFFFAOYSA")  # too short
