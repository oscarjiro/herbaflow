"""Regression: ORM datetime columns must be timezone-aware.

The DB columns are ``timestamp with time zone`` and ``now_utc()`` returns a
tz-aware value. A naive ``datetime`` column binds as ``TIMESTAMP WITHOUT TIME
ZONE``, which makes asyncpg reject the aware value with a DataError — and the
persist services swallow that error, so caching silently never sticks (every
manual target/compound re-hits the provider). These guard against a revert to
the naive declaration.
"""
from app.models.compound import Compound, CompoundAlias, PlantCompound
from app.models.target import CompoundTarget, DiseaseTarget, Target


def _is_tz_aware(model, column: str) -> bool:
    return model.__table__.c[column].type.timezone


def test_target_models_datetime_columns_are_timezone_aware():
    assert _is_tz_aware(Target, "retrieved_at") is True
    assert _is_tz_aware(CompoundTarget, "retrieved_at") is True
    assert _is_tz_aware(DiseaseTarget, "retrieved_at") is True


def test_compound_models_datetime_columns_are_timezone_aware():
    assert _is_tz_aware(Compound, "retrieved_at") is True
    assert _is_tz_aware(CompoundAlias, "retrieved_at") is True
    assert _is_tz_aware(PlantCompound, "retrieved_at") is True
