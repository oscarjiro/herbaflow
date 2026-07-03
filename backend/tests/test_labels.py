"""Unit tests for the shared display-label resolver (app.services.labels)."""

from __future__ import annotations

import uuid

import pytest

from app.services.labels import resolve_entity_labels


class _PlantRow:
    def __init__(self, pid: uuid.UUID, name: str | None) -> None:
        self.plant_id = pid
        self.canonical_scientific_name = name


class _DiseaseRow:
    def __init__(self, did: uuid.UUID, name: str) -> None:
        self.disease_id = did
        self.disease_name = name


class _FakePlantRepo:
    def __init__(self, rows: list[_PlantRow]) -> None:
        self._rows = rows

    async def list_all(self) -> list[_PlantRow]:
        return self._rows


class _FakeDiseaseRepo:
    def __init__(self, rows: list[_DiseaseRow]) -> None:
        self._rows = rows

    async def list_all(self) -> list[_DiseaseRow]:
        return self._rows


P1, P2 = uuid.uuid4(), uuid.uuid4()
D1 = uuid.uuid4()


def _plants() -> _FakePlantRepo:
    return _FakePlantRepo([_PlantRow(P1, "Curcuma longa L."), _PlantRow(P2, "Zingiber officinale")])


def _diseases() -> _FakeDiseaseRepo:
    return _FakeDiseaseRepo([_DiseaseRow(D1, "Type 2 Diabetes Mellitus")])


@pytest.mark.asyncio
async def test_resolves_and_joins_multiple_plants_in_catalog_order() -> None:
    out = await resolve_entity_labels(_plants(), _diseases(), [P2, P1], D1)
    # Joined in catalog order (list_all order), not the requested order.
    assert out == {
        "plant": "Curcuma longa L., Zingiber officinale",
        "disease": "Type 2 Diabetes Mellitus",
    }


@pytest.mark.asyncio
async def test_accepts_string_plant_ids() -> None:
    out = await resolve_entity_labels(_plants(), _diseases(), [str(P1)], None)
    assert out["plant"] == "Curcuma longa L."


@pytest.mark.asyncio
async def test_missing_ids_resolve_to_none() -> None:
    out = await resolve_entity_labels(_plants(), _diseases(), [uuid.uuid4()], uuid.uuid4())
    assert out == {"plant": None, "disease": None}


@pytest.mark.asyncio
async def test_none_sides_are_skipped() -> None:
    out = await resolve_entity_labels(_plants(), _diseases(), None, None)
    assert out == {"plant": None, "disease": None}


@pytest.mark.asyncio
async def test_disease_only() -> None:
    out = await resolve_entity_labels(_plants(), _diseases(), None, D1)
    assert out == {"plant": None, "disease": "Type 2 Diabetes Mellitus"}
