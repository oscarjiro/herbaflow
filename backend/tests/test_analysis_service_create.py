"""Create routing/stamping/pre-fill (entry-modes) — DB-free with fakes.

Drives ``AnalysisService.create`` across the input modes and asserts the kwargs handed to the
(widened) analysis repository: the stage-state stamping, the run cursor (``current_stage`` = first
computed stage), the durable edit-layer pre-fill of user-provided ENTITY stages, and the stored
``input_modes`` / ``labels`` parameters. The fakes mirror the real repo method names the service
calls (``missing_ids`` / ``exists`` / ``existing_ids`` / ``get_many``) and the REAL ``Target`` ORM
attributes (``gene_symbol`` / ``protein_name`` / ``uniprot_accession`` — there is no
``canonical_name`` column on ``targets``).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.schemas.analysis import AnalysisCreate
from app.services.analysis import AnalysisService


class _FakeAnalysisRepo:
    def __init__(self) -> None:
        self.created: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> Any:
        self.created = kwargs

        class _Run:
            analysis_id = uuid.uuid4()
            analysis_name = kwargs["analysis_name"]
            disease_id = kwargs["disease_id"]
            mode = kwargs["mode"]
            status = "pending"
            current_stage = kwargs["current_stage"]
            # Mirror the real (widened) repo parameter layout: base keys, then the
            # extra_parameters spread (input_modes / labels), then the pipeline params.
            parameters = {
                "plant_ids": [str(p) for p in kwargs["plant_ids"]],
                "stage_edits": kwargs.get("stage_edits") or {},
                **(kwargs.get("extra_parameters") or {}),
                **(kwargs.get("pipeline_parameters") or {}),
            }
            stage_results = kwargs.get("stage_results") or {}
            created_at = completed_at = expires_at = updated_at = None
            error_message = None

        return _Run()


class _FakePlantRepo:
    async def missing_ids(self, ids: list[uuid.UUID]) -> list[uuid.UUID]:
        return []


class _FakeDiseaseRepo:
    async def exists(self, did: uuid.UUID) -> bool:
        return True


class _FakeCompoundRepo:
    async def existing_ids(self, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        return set(ids)


class _Target:
    """Mirror of the real ``Target`` ORM attributes (no ``canonical_name`` column)."""

    def __init__(self, tid: uuid.UUID) -> None:
        self.target_id = tid
        self.canonical_key = "P00533"
        self.gene_symbol = "EGFR"
        self.protein_name = "Epidermal growth factor receptor"
        self.uniprot_accession = "P00533"


class _FakeTargetRepo:
    async def existing_ids(self, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        return set(ids)

    async def get_many(self, ids: list[uuid.UUID]) -> list[_Target]:
        return [_Target(i) for i in ids]


def _service(arepo: _FakeAnalysisRepo) -> AnalysisService:
    return AnalysisService(
        plant_repo=_FakePlantRepo(),
        disease_repo=_FakeDiseaseRepo(),
        analysis_repo=arepo,
        compound_repo=_FakeCompoundRepo(),
        target_repo=_FakeTargetRepo(),
    )


@pytest.mark.asyncio
async def test_selection_create_no_prefill() -> None:
    arepo = _FakeAnalysisRepo()
    await _service(arepo).create(AnalysisCreate(plant_ids=[uuid.uuid4()], disease_id=uuid.uuid4()))
    c = arepo.created
    assert c is not None
    assert c["current_stage"] == 1
    assert c["stage_results"] in (None, {})
    assert c["extra_parameters"]["input_modes"] == {"plant": "selection", "disease": "selection"}
    assert "labels" not in c["extra_parameters"]


@pytest.mark.asyncio
async def test_manual_targets_prefills_s3_and_marks_s1_s2_na() -> None:
    arepo = _FakeAnalysisRepo()
    tid = uuid.uuid4()
    await _service(arepo).create(
        AnalysisCreate(
            plant_input_mode="manual_targets",
            manual_target_ids=[tid],
            disease_id=uuid.uuid4(),
            plant_label="custom extract",
        )
    )
    c = arepo.created
    assert c is not None
    assert c["current_stage"] == 4
    sr = c["stage_results"]
    assert sr["1"]["state"] == "not_applicable"
    assert sr["2"]["state"] == "not_applicable"
    assert sr["3"]["state"] == "user_provided"
    row = sr["3"]["targets"][0]
    assert row["gene_symbol"] == "EGFR" and row["uniprot_accession"] == "P00533"
    assert c["stage_edits"]["3"]["added"][0]["target_id"] == str(tid)
    assert c["extra_parameters"]["labels"] == {"plant": "custom extract"}


@pytest.mark.asyncio
async def test_manual_disease_prefills_s4_disease_targets() -> None:
    arepo = _FakeAnalysisRepo()
    tid = uuid.uuid4()
    await _service(arepo).create(
        AnalysisCreate(
            plant_ids=[uuid.uuid4()],
            disease_input_mode="manual_disease_targets",
            manual_disease_target_ids=[tid],
            disease_label="psoriasis",
        )
    )
    c = arepo.created
    assert c is not None
    assert c["current_stage"] == 1
    sr = c["stage_results"]
    assert sr["4"]["state"] == "user_provided"
    # One enriched edit-layer targets list (no separate disease_targets view — B-DUP-2/L-11).
    assert "disease_targets" not in sr["4"]
    t4 = sr["4"]["targets"][0]
    assert t4["target_id"] == str(tid)
    assert t4["gene_symbol"] == "EGFR"
    assert t4["uniprot_accession"] == "P00533"
    # A manual disease-target has no edge -> no score (omitted), but carries the UniProt link.
    assert "score" not in t4
    assert t4["source_url"] == "https://www.uniprot.org/uniprotkb/P00533/entry"
    # S5 reads this targets list directly; the edit layer also seeds stage_edits["4"].
    assert c["stage_edits"]["4"]["added"][0]["target_id"] == str(tid)
    assert c["extra_parameters"]["labels"] == {"disease": "psoriasis"}
