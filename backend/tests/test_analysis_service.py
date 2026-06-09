import uuid

import pytest

from app import contracts
from app.errors import GoneProblem, NotFoundProblem, ValidationProblem
from app.schemas.analysis import AnalysisCreate, Mode
from app.services.analysis import AnalysisService


class FakePlantRepo:
    def __init__(self, missing):
        self._missing = missing

    async def missing_ids(self, plant_ids):
        return self._missing


class FakeDiseaseRepo:
    def __init__(self, exists):
        self._exists = exists

    async def exists(self, disease_id):
        return self._exists


class FakeAnalysisRepo:
    def __init__(self, run=None):
        self.created = None
        self.created_parameters: dict = {}
        self._run = run

    async def create(self, **kwargs):
        from types import SimpleNamespace

        pipeline_parameters = kwargs.get("pipeline_parameters") or {}
        plant_ids = kwargs.get("plant_ids") or []
        manual_compound_ids = kwargs.get("manual_compound_ids") or []
        # Mirror real repo parameter-building so tests assert the stored shape
        self.created_parameters = {
            "plant_ids": [str(p) for p in plant_ids],
            "manual_compounds": [str(c) for c in manual_compound_ids],
            "stage_edits": {},
            **pipeline_parameters,
        }
        self.created = SimpleNamespace(
            analysis_id=uuid.uuid4(),
            analysis_name=kwargs["analysis_name"],
            disease_id=kwargs["disease_id"],
            mode=kwargs["mode"],
            status="pending",
            current_stage=None,
            stage_results={},
            created_at=None,
            completed_at=None,
            expires_at=None,
            error_message=None,
        )
        return self.created

    async def get(self, analysis_id):
        return self._run


class FakeCompoundRepo:
    def __init__(self, existing=None):
        self._existing = set(existing or [])

    async def existing_ids(self, ids):
        return {i for i in ids if i in self._existing}


def _service(plant_missing=None, disease_exists=True, run=None, compound_existing=None):
    return AnalysisService(
        plant_repo=FakePlantRepo(plant_missing or []),
        disease_repo=FakeDiseaseRepo(disease_exists),
        analysis_repo=FakeAnalysisRepo(run),
        compound_repo=FakeCompoundRepo(compound_existing or []),
    )


@pytest.mark.asyncio
async def test_create_rejects_unknown_plants() -> None:
    bad = uuid.uuid4()
    svc = _service(plant_missing=[bad])
    payload = AnalysisCreate(plant_ids=[bad], disease_id=uuid.uuid4(), mode=Mode.auto)
    with pytest.raises(ValidationProblem):
        await svc.create(payload)


@pytest.mark.asyncio
async def test_create_rejects_unknown_disease() -> None:
    svc = _service(disease_exists=False)
    payload = AnalysisCreate(plant_ids=[uuid.uuid4()], disease_id=uuid.uuid4())
    with pytest.raises(ValidationProblem):
        await svc.create(payload)


def test_create_default_mode_matches_contract() -> None:
    payload = AnalysisCreate(plant_ids=[uuid.uuid4()], disease_id=uuid.uuid4())
    assert payload.mode.value == contracts.default_mode()
    assert payload.mode.value == "guided"


@pytest.mark.asyncio
async def test_create_rejects_unknown_manual_compounds() -> None:
    svc = _service(compound_existing=[])
    bad = uuid.uuid4()
    payload = AnalysisCreate(
        plant_ids=[uuid.uuid4()],
        disease_id=uuid.uuid4(),
        mode=Mode.auto,
        manual_compound_ids=[bad],
    )
    with pytest.raises(ValidationProblem):
        await svc.create(payload)


@pytest.mark.asyncio
async def test_get_unknown_is_404() -> None:
    svc = _service(run=None)
    with pytest.raises(NotFoundProblem):
        await svc.get(uuid.uuid4())


@pytest.mark.asyncio
async def test_get_expired_is_410() -> None:
    from datetime import timedelta
    from types import SimpleNamespace

    from app.clock import now_utc

    expired = SimpleNamespace(expires_at=now_utc() - timedelta(hours=1))
    svc = _service(run=expired)
    with pytest.raises(GoneProblem):
        await svc.get(uuid.uuid4())


@pytest.mark.asyncio
async def test_create_freezes_adme_defaults() -> None:
    P = uuid.uuid4()
    D = uuid.uuid4()
    svc = _service()
    # Access the underlying fake repo so we can inspect what was passed
    fake_analysis_repo = svc.analysis_repo
    await svc.create(AnalysisCreate(plant_ids=[P], disease_id=D))
    assert fake_analysis_repo.created_parameters.get("adme") == contracts.adme_defaults()
    assert fake_analysis_repo.created_parameters.get("stage_edits") == {}
