from sqlalchemy import DateTime

from app.models import ALL_TABLES


def test_all_datetime_columns_are_timezone_aware() -> None:
    offenders = []
    for table in ALL_TABLES:
        for column in table.columns:
            if isinstance(column.type, DateTime) and not column.type.timezone:
                offenders.append(f"{table.name}.{column.name}")
    assert offenders == [], f"naive datetime columns: {offenders}"


def test_expected_tables_present() -> None:
    names = {t.name for t in ALL_TABLES}
    assert {"diseases", "plants", "compounds", "plant_compounds", "analysis_runs"} <= names
