import app.services.canonical as c


def test_alias_helpers_removed():
    for gone in (
        "plant_alias_id",
        "compound_alias_id",
        "target_alias_id",
        "disease_alias_id",
        "pick_alias",
        "ALIAS_PRIORITY",
    ):
        assert not hasattr(c, gone), gone
