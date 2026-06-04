# backend/tests/unit/test_create_with_inputs.py
import types
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.schemas.analysis import CreateAnalysisRequest, InjectCompoundsResponse


def _fake_run():
    run = AsyncMock()
    run.analysis_id = uuid.uuid4()
    run.status = "pending"
    run.mode = "guided"
    run.current_stage = None
    run.created_at = None
    run.updated_at = None
    return run


@pytest.mark.asyncio
async def test_create_injects_before_scheduling_pipeline():
    """Compounds are injected synchronously; the pipeline is scheduled only after."""
    order: list[str] = []

    async def fake_inject(compounds, run, session):
        order.append("inject")
        return InjectCompoundsResponse(
            injected=len(compounds), failed=[], duplicates_removed=0,
            duplicate_names=[], cached=0,
        )

    class FakeBG:
        def add_task(self, *a, **k):
            order.append("schedule")

    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(return_value=_fake_run())), \
         patch("app.services.manual_inputs.inject_compounds_service", new=AsyncMock(side_effect=fake_inject)):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": [], "disease_id": "d1",
             "compounds": ["CCO"], "parameters": {}})
        await analyses.create_analysis(None, body, FakeBG(), session=AsyncMock())

    assert order == ["inject", "schedule"]


@pytest.mark.asyncio
async def test_standard_mode_schedules_without_inject():
    scheduled = []

    class FakeBG:
        def add_task(self, *a, **k): scheduled.append(a)

    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(return_value=_fake_run())):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": ["p1"], "disease_id": "d1",
             "parameters": {}})
        await analyses.create_analysis(None, body, FakeBG(), session=AsyncMock())

    assert len(scheduled) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("skip", [True, False])
async def test_create_forwards_skip_validation_to_inject_targets(skip):
    """The request's skip_validation flag reaches inject_targets_service so a caller can
    opt into lenient offline-HGNC injection instead of the strict UniProt round-trip."""
    captured = {}

    async def fake_inject(targets, skip_validation, run, session):
        captured["skip_validation"] = skip_validation
        return types.SimpleNamespace(injected=len(targets))

    class FakeBG:
        def add_task(self, *a, **k): pass

    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(return_value=_fake_run())), \
         patch("app.services.manual_inputs.inject_targets_service", new=AsyncMock(side_effect=fake_inject)):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": [], "disease_id": "d1",
             "targets": ["AKT1"], "skip_validation": skip, "parameters": {}})
        await analyses.create_analysis(None, body, FakeBG(), session=AsyncMock())

    assert captured["skip_validation"] is skip


@pytest.mark.asyncio
async def test_manual_disease_targets_persisted_into_stored_parameters():
    """Server resolves manual_disease_targets at create time (via resolve_targets) and
    stores the RESOLVED DICTS — not the raw strings — under _injected_disease_targets,
    alongside _disease_input_mode='manual_targets'.

    resolve_targets is mocked with a canned ResolveResult so the test stays offline
    (no UniProt round-trip)."""
    from app.services.input_validation import ResolveResult

    captured = {}

    async def capture_create(session, name, mode, parameters, disease_id=None):
        captured["parameters"] = parameters
        captured["disease_id"] = disease_id
        return _fake_run()

    resolved = [
        {"target_id": "uuid-tp53", "gene_symbol": "TP53", "uniprot_id": "P04637",
         "protein_name": "Cellular tumor antigen p53", "compound_ids": [], "sources": ["manual"]},
        {"target_id": "uuid-egfr", "gene_symbol": "EGFR", "uniprot_id": "P00533",
         "protein_name": "Epidermal growth factor receptor", "compound_ids": [], "sources": ["manual"]},
    ]
    canned = ResolveResult(valid=resolved, enriched=2)

    class FakeBG:
        def add_task(self, *a, **k): pass

    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(side_effect=capture_create)), \
         patch("app.services.input_validation.resolve_targets", new=AsyncMock(return_value=canned)):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": ["p1"], "disease_id": None,
             "manual_disease_targets": ["TP53", "EGFR"], "parameters": {}})
        await analyses.create_analysis(None, body, FakeBG(), session=AsyncMock())

    p = captured["parameters"]
    assert p["_disease_input_mode"] == "manual_targets"
    # Now the resolved dicts, not raw strings
    assert p["_injected_disease_targets"] == resolved


class _ExecResult:
    """Mimics ``await session.exec(stmt)`` — exposes ``.first()``."""

    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    """Async session stub: every DB-first lookup is a miss (returns None)."""

    async def exec(self, _stmt):
        return _ExecResult(None)

    def add(self, _obj):
        pass

    async def commit(self):
        pass


def _make_uniprot_target(gene, accession, protein_name=None):
    from unittest.mock import MagicMock
    t = MagicMock()
    t.gene_symbol = gene
    t.uniprot_accession = accession
    t.protein_name = protein_name
    return t


@pytest.mark.asyncio
async def test_manual_disease_target_accession_resolves_to_gene_symbol():
    """REGRESSION: a UniProt accession in manual_disease_targets must be RESOLVED to its
    gene symbol at create time — not stored verbatim as a bogus gene symbol.

    Before the unified-resolution rewire, '_injected_disease_targets' held the raw
    strings, so a UniProt accession (P04637) leaked downstream as a fake gene symbol.
    Now create_analysis runs resolve_targets, which resolves P04637 → TP53. We drive
    the REAL resolve_targets (DB miss via _FakeSession) and only mock the UniProt
    round-trip so the test is deterministic and offline."""
    from app.services import gene_symbols

    captured = {}

    async def capture_create(session, name, mode, parameters, disease_id=None):
        captured["parameters"] = parameters
        return _fake_run()

    class FakeBG:
        def add_task(self, *a, **k): pass

    gene_symbols._MAP = {"TP53": {"symbol": "TP53", "kind": "approved"}}
    try:
        from app.routers import analyses
        with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(side_effect=capture_create)), \
             patch("app.services.input_validation.validate_human_target",
                   new=AsyncMock(return_value=_make_uniprot_target("TP53", "P04637", "Cellular tumor antigen p53"))), \
             patch("app.services.input_validation.persist_validated_targets", new=AsyncMock(return_value=1)):
            body = CreateAnalysisRequest.model_validate(
                {"name": "n", "mode": "guided", "plant_ids": ["p1"], "disease_id": None,
                 "manual_disease_targets": ["P04637"], "parameters": {}})
            await analyses.create_analysis(None, body, FakeBG(), session=_FakeSession())
    finally:
        gene_symbols._MAP = None

    p = captured["parameters"]
    assert p["_disease_input_mode"] == "manual_targets"
    injected = p["_injected_disease_targets"]
    assert len(injected) == 1
    d = injected[0]
    # The bug being fixed: P04637 must NOT survive as the gene symbol.
    assert d["gene_symbol"] == "TP53"
    assert d["gene_symbol"] != "P04637"
    assert d["uniprot_id"] == "P04637"


@pytest.mark.asyncio
async def test_manual_disease_targets_uniprot_outage_maps_to_503():
    """A provider outage while resolving manual_disease_targets at create time surfaces
    as HTTP 503 (mirroring the inject-targets path)."""
    from fastapi import HTTPException
    from integrations._retry import ServiceUnavailableError

    class FakeBG:
        def add_task(self, *a, **k): pass

    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(side_effect=AssertionError("must not create on outage"))), \
         patch("app.services.input_validation.validate_human_target",
               new=AsyncMock(side_effect=ServiceUnavailableError("UniProt down"))):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": ["p1"], "disease_id": None,
             "manual_disease_targets": ["P04637"], "parameters": {}})
        with pytest.raises(HTTPException) as ei:
            await analyses.create_analysis(None, body, FakeBG(), session=_FakeSession())
    assert ei.value.status_code == 503


@pytest.mark.asyncio
async def test_all_invalid_compounds_deletes_run_and_422_no_schedule():
    """All-invalid manual input -> 422, the created run is deleted, pipeline NOT scheduled."""
    from fastapi import HTTPException
    scheduled = []
    deleted = []

    async def fake_inject(compounds, run, session):
        return InjectCompoundsResponse(
            injected=0, failed=list(compounds), duplicates_removed=0,
            duplicate_names=[], cached=0,
        )

    class FakeBG:
        def add_task(self, *a, **k): scheduled.append(a)

    run = _fake_run()
    from app.routers import analyses
    with patch.object(analyses.analysis_repo, "create_run", new=AsyncMock(return_value=run)), \
         patch.object(analyses.analysis_repo, "delete_run", new=AsyncMock(side_effect=lambda s, aid: deleted.append(aid))), \
         patch("app.services.manual_inputs.inject_compounds_service", new=AsyncMock(side_effect=fake_inject)):
        body = CreateAnalysisRequest.model_validate(
            {"name": "n", "mode": "guided", "plant_ids": [], "disease_id": "d1",
             "compounds": ["bad"], "parameters": {}})
        with pytest.raises(HTTPException) as ei:
            await analyses.create_analysis(None, body, FakeBG(), session=AsyncMock())
    assert ei.value.status_code == 422
    assert deleted == [run.analysis_id]
    assert scheduled == []


# ---------------------------------------------------------------------------
# Test: inject_compounds_service stamps stage_1 as user_provided + inputs;
#       the synthetic stage_2 must NOT be written.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_compounds_stamps_user_provided_and_drops_stage2():
    """stage_1 gains state='user_provided' + inputs.rejected; stage_2 is never written.

    inject_compounds_service now routes through the unified ``resolve_compounds``
    service (imported into manual_inputs), so we patch that with a canned
    ``ResolveResult`` instead of the old validate/dedup pair.
    """
    from unittest.mock import MagicMock, patch

    from app.services.input_validation import LineFailure, ResolveResult
    from app.services.manual_inputs import inject_compounds_service

    run = MagicMock()
    run.analysis_id = uuid.uuid4()
    run.status = "pending"
    run.stage_results = {}
    run.parameters = {}

    # One validated compound, one failed raw string
    validated_compound = {
        "compound_id": str(uuid.uuid4()),
        "canonical_name": "Ethanol",
        "canonical_key": "pubchem:702",
        "pubchem_cid": 702,
        "adme_pass": True,
        "is_np_exception": False,
        "is_pains_positive": False,
        "molecular_weight": 46.07,
        "logp": -0.14,
        "tpsa": 20.23,
        "hbond_donors": 1,
        "hbond_acceptors": 1,
        "np_likeness_score": -1.0,
        "rotatable_bonds": 0,
    }
    failed_input = "BADINPUT"

    written_stage_results: dict = {}

    async def fake_update(session, analysis_id, status, **kwargs):
        if "stage_results" in kwargs:
            written_stage_results.update(kwargs["stage_results"])

    canned = ResolveResult(
        valid=[validated_compound],
        failed=[LineFailure(line=2, input=failed_input, reason="not found in PubChem")],
        enriched=1,
    )

    mock_session = MagicMock()

    with patch("app.services.manual_inputs.resolve_compounds",
               new=AsyncMock(return_value=canned)), \
         patch("app.services.manual_inputs.analysis_repo.update_run_status",
               new=AsyncMock(side_effect=fake_update)), \
         patch("app.services.manual_inputs.analysis_repo.merge_run_parameters",
               new=AsyncMock()):

        await inject_compounds_service(
            compounds=["ETHANOL", failed_input],
            run=run,
            session=mock_session,
        )

    stage1 = written_stage_results.get("stage_1", {})

    assert stage1["state"] == "user_provided"
    assert stage1["inputs"]["rejected"] == ["BADINPUT"]
    assert "stage_2" not in written_stage_results  # synthetic stage_2 dropped
