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
        # Mirror real repo parameter-building so tests assert the stored shape
        self.created_parameters = {
            "plant_ids": [str(p) for p in plant_ids],
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

    async def get_many(self, ids):
        from types import SimpleNamespace

        return [
            SimpleNamespace(
                compound_id=i,
                canonical_name=f"compound-{i}",
                inchi_key=f"INCHIKEY-{str(i)[:8]}",
                smiles="CCO",
                source_url=(
                    "https://pubchem.ncbi.nlm.nih.gov/compound/" f"{str(i).replace('-', '')[:8]}"
                ),
            )
            for i in ids
        ]


def _service(plant_missing=None, disease_exists=True, run=None, compound_existing=None):
    return AnalysisService(
        plant_repo=FakePlantRepo(plant_missing or []),
        disease_repo=FakeDiseaseRepo(disease_exists),
        analysis_repo=FakeAnalysisRepo(run),
        compound_repo=FakeCompoundRepo(compound_existing or []),
    )


def test_target_add_entry_carries_uniprot_source_url() -> None:
    """The shared target identity entry carries a UniProt ``source_url`` derived from the accession.

    Single home for target identity used by the S3 + S4 prefills AND the edit-add path, so every
    target row (created or added, plant or disease side) renders a UniProt link symmetrically — no
    per-call source_url duplication (B2-sym).
    """
    from types import SimpleNamespace

    t = SimpleNamespace(
        target_id=uuid.uuid4(),
        gene_symbol="AKT1",
        protein_name="RAC-alpha serine/threonine-protein kinase",
        uniprot_accession="P31749",
    )
    entry = AnalysisService._target_add_entry(t)
    assert entry["uniprot_accession"] == "P31749"
    assert entry["gene_symbol"] == "AKT1"
    assert entry["source_url"] == "https://www.uniprot.org/uniprotkb/P31749/entry"


def test_target_add_entry_source_url_none_without_accession() -> None:
    """No accession → no UniProt link (honest null, not a broken URL)."""
    from types import SimpleNamespace

    t = SimpleNamespace(
        target_id=uuid.uuid4(), gene_symbol="X", protein_name=None, uniprot_accession=None
    )
    assert AnalysisService._target_add_entry(t)["source_url"] is None


def test_compound_add_entry_carries_structure_and_source_url() -> None:
    """The shared compound edit entry carries Stage-1 identity fields for manual/user-added rows."""
    from types import SimpleNamespace

    cid = uuid.uuid4()
    c = SimpleNamespace(
        compound_id=cid,
        canonical_name="Curcumin",
        inchi_key="VFLDPWHFBUODDF-FCXRPNKRSA-N",
        smiles="COc1cc(O)ccc1",
        source_url="https://pubchem.ncbi.nlm.nih.gov/compound/969516",
    )
    entry = AnalysisService._compound_add_entry(c)
    assert entry["compound_id"] == str(cid)
    assert entry["canonical_name"] == "Curcumin"
    assert entry["inchikey"] == "VFLDPWHFBUODDF-FCXRPNKRSA-N"
    assert entry["smiles"] == "COc1cc(O)ccc1"
    assert entry["source_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/969516"


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
    # manual_compounds mode: unknown compound id → service rejects.
    svc = _service(compound_existing=[])
    bad = uuid.uuid4()
    payload = AnalysisCreate(
        plant_input_mode="manual_compounds",
        disease_id=uuid.uuid4(),
        mode=Mode.auto,
        manual_compound_ids=[bad],
    )
    with pytest.raises(ValidationProblem):
        await svc.create(payload)


@pytest.mark.asyncio
async def test_create_rejects_too_many_manual_compounds() -> None:
    # The manual-compound cap (RS.2: max 2000) is enforced before the existence check,
    # so an overflow is rejected without touching the compound repo.
    over = contracts.max_compounds() + 1
    ids = [uuid.uuid4() for _ in range(over)]
    svc = _service(compound_existing=ids)  # all "exist" — only the cap should reject
    payload = AnalysisCreate(
        plant_input_mode="manual_compounds",
        disease_id=uuid.uuid4(),
        mode=Mode.auto,
        manual_compound_ids=ids,
    )
    with pytest.raises(ValidationProblem) as e:
        await svc.create(payload)
    assert str(contracts.max_compounds()) in (e.value.detail or "")


@pytest.mark.asyncio
async def test_create_allows_manual_compounds_at_cap() -> None:
    # Exactly the cap is allowed (no off-by-one); existence still validated.
    at_cap = contracts.max_compounds()
    ids = [uuid.uuid4() for _ in range(at_cap)]
    svc = _service(compound_existing=ids)
    payload = AnalysisCreate(
        plant_input_mode="manual_compounds",
        disease_id=uuid.uuid4(),
        mode=Mode.auto,
        manual_compound_ids=ids,
    )
    result, _ = await svc.create(payload)
    assert result is not None


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
    # Stage 4's disease_targets defaults are frozen into the run parameters at create too.
    assert fake_analysis_repo.created_parameters.get("disease_targets") == {"min_score": 0.3}
    assert fake_analysis_repo.created_parameters.get("stage_edits") == {}
