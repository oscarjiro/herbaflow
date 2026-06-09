"""Smoke tests: verify ORM model table bindings and datetime timezone-awareness."""


def test_target_and_edge_models_map() -> None:
    from app.models.compound_target import CompoundTarget
    from app.models.target import Target

    assert Target.__tablename__ == "targets"
    assert CompoundTarget.__tablename__ == "compound_targets"
    assert Target.__table__.c.retrieved_at.type.timezone is True
    assert CompoundTarget.__table__.c.retrieved_at.type.timezone is True
