import uuid

from app.pipeline.stages import stage1


def _row(plant_id, compound_id, name):
    return stage1.CompoundRow(plant_id=plant_id, compound_id=compound_id, canonical_name=name)


def test_select_dedupes_and_attributes() -> None:
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    rows = [_row(p1, c1, "a"), _row(p1, c2, "b"), _row(p2, c1, "a")]

    result = stage1.select_compounds(rows)

    assert result["count"] == 2
    assert result["state"] == "computed"
    assert {c["compound_id"] for c in result["compounds"]} == {str(c1), str(c2)}
    assert set(result["per_plant"][str(p1)]) == {str(c1), str(c2)}
    assert result["per_plant"][str(p2)] == [str(c1)]


def test_select_empty_is_zero() -> None:
    result = stage1.select_compounds([])
    assert result["count"] == 0
    assert result["compounds"] == []
