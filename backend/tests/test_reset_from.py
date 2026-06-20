"""Guided-machinery tests: dependency-aware reset_from + durable in-stage edit layer.

Edge cases:
- E1: reset_from / edit on a non-settled run -> 409.
- E7: param Redo with overrides EQUAL to the frozen group -> no clear, no re-run.
- param Redo (changing a value) clears {2} and re-runs from 2; writes the override.
- param override out of HARD range -> 422; advisory recommended range is NOT enforced.
- set edit S1 clears downstream {2}, re-runs from 2 (NOT 1); the S1 stored result tags the edit.
- E6 end-to-end: edit S1 (add) -> S2 includes it; then param Redo S2 -> the S1 add survives.
- E2: a re-run that raises leaves cleared-downstream cleared and the run failed.
- never-empty: edit S1 removing every compound is rejected (422); nothing persisted, no S2 re-run.
- cap: edit_stage add beyond the compound cap -> 422 with the cap.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app import contracts
from app.errors import ConflictProblem, ValidationProblem
from app.pipeline import edits, engine
from app.pipeline.stages import stage5
from app.services.analysis import AnalysisService


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeRepo:
    """Dict-backed fake of AnalysisRepository, mirroring its jsonb-dirty pattern."""

    def __init__(self, run: SimpleNamespace) -> None:
        self.run = run
        self.session = SimpleNamespace()  # build_runners(session) only needs an object
        self.cleared: list[set[int]] = []

    async def get(self, analysis_id: uuid.UUID) -> SimpleNamespace:
        return self.run

    async def set_status(
        self, run: SimpleNamespace, status: str, *, current_stage: int | None = None
    ) -> None:
        run.status = status
        if current_stage is not None:
            run.current_stage = current_stage

    async def set_stage_result(self, run: SimpleNamespace, stage: int, result: dict) -> None:
        merged = dict(run.stage_results)
        merged[str(stage)] = result
        run.stage_results = merged

    async def clear_stage_results(self, run: SimpleNamespace, stages: set[int]) -> None:
        self.cleared.append(set(stages))
        merged = {k: v for k, v in run.stage_results.items() if int(k) not in stages}
        run.stage_results = merged

    async def mark_stages_stale(self, run: SimpleNamespace, stages: set[int]) -> None:
        merged = dict(run.stage_results)
        for s in stages:
            key = str(s)
            if key in merged:
                merged[key] = {**merged[key], "stale": True}
        run.stage_results = merged

    async def set_parameters(self, run: SimpleNamespace) -> None:
        return None

    async def complete(self, run: SimpleNamespace) -> None:
        run.status = "complete"

    async def fail(self, run: SimpleNamespace, message: str) -> None:
        run.status = "failed"
        run.error_message = message

    async def commit(self) -> None:
        pass


class FakeCompoundRepo:
    def __init__(self, names: dict[uuid.UUID, str]) -> None:
        self._names = names

    async def existing_ids(self, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        return {i for i in ids if i in self._names}

    async def get_many(self, ids: list[uuid.UUID]) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(compound_id=i, canonical_name=self._names[i])
            for i in ids
            if i in self._names
        ]


def _adme() -> dict[str, Any]:
    return dict(contracts.adme_defaults())


def _stage1_fragment(ids: list[str]) -> dict[str, Any]:
    """A freshly-computed (no edit) S1 stored fragment for the given computed ids."""
    entities = [{"compound_id": i, "canonical_name": f"C-{i[-2:]}"} for i in ids]
    return edits.build_stage_entities(entities, None)


def _hub_genes() -> dict[str, Any]:
    return {"top_n": 20}


def _enrichment() -> dict[str, Any]:
    return {
        "significance_threshold": 0.05,
        "sources": ["GO:BP", "KEGG"],
        "correction": "fdr",
        "min_term_size": 5,
    }


def _run(*, computed: list[str], mode: str = "auto") -> SimpleNamespace:
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        mode=mode,
        status="complete",
        current_stage=2,
        error_message=None,
        parameters={
            "plant_ids": [str(uuid.uuid4())],
            "manual_compounds": [],
            "stage_edits": {},
            "adme": _adme(),
            "hub_genes": _hub_genes(),
            "enrichment": _enrichment(),
        },
        stage_results={
            "1": _stage1_fragment(computed),
            "2": {"count": len(computed), "passed": [], "filtered": [], "state": "computed"},
            # A completed run carries S3/S4 (their target sets share t0 so a pulled-in S5
            # re-run finds a non-empty overlap rather than terminal-failing on KeyError).
            "3": {
                "targets": [{"target_id": "t0", "canonical_name": "T0"}],
                "count": 1,
                "state": "computed",
            },
            "4": {
                "targets": [{"target_id": "t0", "score": 0.5}],
                "count": 1,
                "state": "computed",
            },
        },
    )


def _service(run: SimpleNamespace, names: dict[uuid.UUID, str]) -> AnalysisService:
    repo = FakeRepo(run)
    return AnalysisService(
        plant_repo=SimpleNamespace(),
        disease_repo=SimpleNamespace(),
        analysis_repo=repo,
        compound_repo=FakeCompoundRepo(names),
    )


def _patch_runners(monkeypatch: pytest.MonkeyPatch, **counts: int) -> dict[str, list]:
    """Replace engine.build_runners with stage runners that record calls.

    stage1 emits a computed fragment from the *effective* S1 set already stored (it is
    never recomputed in this chunk); stage2 emits a count = size of the effective S1 set.
    """
    calls: dict[str, list] = {
        "1": [],
        "2": [],
        "3": [],
        "4": [],
        "5": [],
        "6": [],
        "7": [],
        "8": [],
    }

    def fake_build_runners(session: Any) -> dict[int, Any]:
        async def stage1_runner(run: SimpleNamespace) -> dict:
            calls["1"].append(True)
            # Recompute would re-emit the computed ids; return the stored computed set.
            ids = run.stage_results["1"]["computed_ids"]
            entities = [{"compound_id": i, "canonical_name": f"C-{i[-2:]}"} for i in ids]
            return {**edits.build_stage_entities(entities, None)}

        async def stage2_runner(run: SimpleNamespace) -> dict:
            effective = [
                c for c in run.stage_results["1"]["compounds"] if c["tag"] != "user-removed"
            ]
            calls["2"].append([c["compound_id"] for c in effective])
            return {
                "count": len(effective),
                "passed": [{"compound_id": c["compound_id"]} for c in effective],
                "filtered": [],
                "annotations": {},
                "state": "computed",
            }

        async def stage3_runner(run: SimpleNamespace) -> dict:
            passed = run.stage_results["2"]["passed"]
            calls["3"].append([p["compound_id"] for p in passed])
            return {
                "targets": [{"target_id": "t0", "canonical_name": "T0"}],
                "compound_targets": [],
                "per_compound": {},
                "coverage_pct": 0.0,
                "count": 1,
                "state": "computed",
            }

        async def stage4_runner(run: SimpleNamespace) -> dict:
            # Disease-side read; independent of the compound chain (idempotent S4 re-run).
            calls["4"].append(True)
            return {
                "targets": [{"target_id": "t0", "canonical_name": "T0", "score": 0.5}],
                "count": 1,
                "min_score_applied": 0.3,
                "state": "computed",
            }

        async def stage5_runner(run: SimpleNamespace) -> dict:
            # Overlap of the stored S3 / S4 target sets (both carry t0 -> count 1).
            calls["5"].append(True)
            return await stage5.run(None, run)

        async def stage6_runner(run: SimpleNamespace) -> dict:
            # Ready-made computed PPI result (no STRING call) -> count 1.
            calls["6"].append(True)
            return {
                "state": "computed",
                "nodes": [
                    {
                        "gene_symbol": "G0",
                        "target_id": "t0",
                        "uniprot_accession": None,
                        "string_id": None,
                    },
                ],
                "edges": [],
                "node_count": 1,
                "edge_count": 0,
                "count": 1,
            }

        async def stage7_runner(run: SimpleNamespace) -> dict:
            # Hub-ranking fake: one hub from the stage-6 single node (no networkx call needed).
            calls["7"].append(True)
            return {
                "state": "computed",
                "hubs": [
                    {
                        "rank": 1,
                        "gene_symbol": "G0",
                        "target_id": "t0",
                        "degree": 0,
                        "betweenness": 0,
                        "closeness": 0,
                        "eigenvector": 0,
                        "mcc": 0,
                        "source_url": None,
                    }
                ],
                "ranking_metric": "mcc",
                "node_count": 1,
                "top_n": 20,
                "count": 1,
                "flags": ["network_too_small"],
            }

        async def stage8_runner(run: SimpleNamespace) -> dict:
            # Enrichment fake: honest null — valid terminal completion.
            calls["8"].append(True)
            return {
                "state": "computed",
                "terms": [],
                "count": 0,
                "degraded": False,
                "flags": ["empty_input"],
                "input_gene_count": 0,
                "background_gene_count": 1,
                "background_source": "compound_target_universe",
                "correction": "fdr",
                "significance_threshold": 0.05,
                "min_term_size": 5,
                "sources": ["GO:BP"],
            }

        return {
            1: stage1_runner,
            2: stage2_runner,
            3: stage3_runner,
            4: stage4_runner,
            5: stage5_runner,
            6: stage6_runner,
            7: stage7_runner,
            8: stage8_runner,
        }

    monkeypatch.setattr(engine, "build_runners", fake_build_runners)
    return calls


# ---------------------------------------------------------------------------
# E1 — non-settled guard
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reset_from_on_running_run_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_runners(monkeypatch)
    run = _run(computed=["a", "b"])
    run.status = "stage_1_running"
    svc = _service(run, {})
    with pytest.raises(ConflictProblem):
        await svc.reset_from(run.analysis_id, 2, {"max_violations": 0})


@pytest.mark.asyncio
async def test_edit_on_running_run_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_runners(monkeypatch)
    run = _run(computed=["a", "b"])
    run.status = "stage_2_running"
    svc = _service(run, {})
    with pytest.raises(ConflictProblem):
        await svc.edit_stage(run.analysis_id, 1, add=[], remove=[])


# ---------------------------------------------------------------------------
# E7 — param Redo no-op
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_param_redo_equal_to_frozen_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_runners(monkeypatch)
    run = _run(computed=["a", "b"])
    before = dict(run.stage_results)
    svc = _service(run, {})
    repo = svc.analysis_repo

    await svc.reset_from(run.analysis_id, 2, dict(_adme()))  # equal to frozen

    assert repo.cleared == []  # no clear
    assert calls["2"] == []  # no re-run
    assert run.stage_results == before


# ---------------------------------------------------------------------------
# param Redo (changing a value) — clears {2}, re-runs from 2, writes the override
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_param_redo_change_clears_2_and_reruns(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_runners(monkeypatch)
    run = _run(computed=["a", "b"])
    svc = _service(run, {})
    repo = svc.analysis_repo

    await svc.reset_from(run.analysis_id, 2, {"max_violations": 0})

    # param Redo of S2 clears its produced downstream closure (2 + the produced 3); S5 and S6
    # are in the closure but were not produced, so they are re-run (S4 is read from its stored
    # result).
    assert {2, 3} in repo.cleared
    assert len(calls["2"]) == 1  # re-ran stage 2
    assert len(calls["5"]) == 1  # re-ran stage 5 (pulled in via the S3->S5 dependency)
    assert len(calls["6"]) == 1  # re-ran stage 6 (pulled in via the S5->S6 dependency)
    assert calls["1"] == []  # did NOT re-run stage 1
    assert run.parameters["adme"]["max_violations"] == 0
    assert run.status == "complete"


# ---------------------------------------------------------------------------
# param override range enforcement (hard only; advisory not enforced)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_param_override_below_hard_min_is_422(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_runners(monkeypatch)
    run = _run(computed=["a", "b"])
    svc = _service(run, {})
    with pytest.raises(ValidationProblem):
        await svc.reset_from(run.analysis_id, 2, {"max_mw": -1})  # exclusiveMinimum 0


@pytest.mark.asyncio
async def test_param_override_outside_recommended_but_in_hard_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_runners(monkeypatch)
    run = _run(computed=["a", "b"])
    svc = _service(run, {})
    # max_mw 1500 is outside recommended 350-600 but within hard 0..2000 -> accepted.
    await svc.reset_from(run.analysis_id, 2, {"max_mw": 1500})
    assert run.parameters["adme"]["max_mw"] == 1500
    assert len(calls["2"]) == 1


# ---------------------------------------------------------------------------
# set edit S1 — stages the change: marks S2 stale, runs nothing, records rerun_from
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_set_edit_s1_marks_s2_stale_without_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_runners(monkeypatch)
    run = _run(computed=["a", "b", "c"])
    rid = uuid.uuid4()
    run.stage_results["1"]["compounds"][1]["compound_id"] = str(rid)
    run.stage_results["1"]["computed_ids"][1] = str(rid)
    svc = _service(run, {})
    repo = svc.analysis_repo

    await svc.edit_stage(run.analysis_id, 1, add=[], remove=[rid])

    assert calls["1"] == [] and calls["2"] == []  # nothing re-ran
    assert repo.cleared == []  # nothing cleared
    assert run.stage_results["2"]["stale"] is True  # downstream flagged
    assert run.parameters["rerun_from"] == 1  # confirm target recorded
    s1 = run.stage_results["1"]
    removed = next(c for c in s1["compounds"] if c["compound_id"] == str(rid))
    assert removed["tag"] == "user-removed"  # edit still applied in place
    assert s1.get("stale") is None  # the edited stage itself is fresh
    assert s1["count"] == 2


# ---------------------------------------------------------------------------
# Guided edit of the CURRENT awaiting stage re-parks (must NOT advance past its checkpoint)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_guided_edit_of_current_awaiting_stage_reparks_without_advancing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_runners(monkeypatch)
    # Guided run parked awaiting approval AT stage 1 (S2 not computed yet).
    run = SimpleNamespace(
        analysis_id=uuid.uuid4(),
        mode="guided",
        status="stage_1_awaiting_approval",
        current_stage=1,
        error_message=None,
        parameters={
            "plant_ids": [str(uuid.uuid4())],
            "manual_compounds": [],
            "stage_edits": {},
            "adme": _adme(),
        },
        stage_results={"1": _stage1_fragment(["a", "b"])},
    )
    new_id = uuid.uuid4()
    svc = _service(run, {new_id: "NewCompound"})

    await svc.edit_stage(run.analysis_id, 1, add=[new_id], remove=[])

    # The added compound is folded into S1's set...
    s1 = run.stage_results["1"]
    assert any(c["compound_id"] == str(new_id) for c in s1["compounds"])
    # ...but the run STAYS parked at S1: an edit of the current checkpoint must not
    # advance past it (no implicit approve, no S2 run).
    assert run.status == "stage_1_awaiting_approval"
    assert run.current_stage == 1
    assert calls["2"] == []
    assert run.stage_results["1"].get("stale") is None  # edited stage is fresh
    assert "2" not in run.stage_results  # nothing downstream existed to stale
    assert "rerun_from" not in run.parameters  # no downstream -> no confirm target


# ---------------------------------------------------------------------------
# E6 end-to-end — edit S1 add survives a later S2 param Redo
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_e6_s1_add_survives_a_later_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_runners(monkeypatch)
    run = _run(computed=["a", "b"])
    new_id = uuid.uuid4()
    svc = _service(run, {new_id: "NewCompound"})

    # Stage an S1 add: applied in place, S2 marked stale, nothing re-runs.
    await svc.edit_stage(run.analysis_id, 1, add=[new_id], remove=[])
    s1 = run.stage_results["1"]
    assert any(c["compound_id"] == str(new_id) for c in s1["compounds"])
    assert run.stage_results["2"]["stale"] is True
    assert calls["2"] == []

    # Confirm with an explicit reset-from/2 param Redo: it runs, and the S1 add survives.
    await svc.reset_from(run.analysis_id, 2, {"max_violations": 0})
    s1_after = run.stage_results["1"]
    still = next(c for c in s1_after["compounds"] if c["compound_id"] == str(new_id))
    assert still["tag"] == "user-added"
    assert str(new_id) in calls["2"][-1]  # the re-run screened the added compound


# ---------------------------------------------------------------------------
# E2 — re-run that raises leaves downstream cleared and run failed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_e2_rerun_failure_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_build_runners(session: Any) -> dict[int, Any]:
        async def stage1_runner(run: SimpleNamespace) -> dict:
            ids = run.stage_results["1"]["computed_ids"]
            entities = [{"compound_id": i, "canonical_name": "x"} for i in ids]
            return {**edits.build_stage_entities(entities, None)}

        async def stage2_runner(run: SimpleNamespace) -> dict:
            raise RuntimeError("provider outage")

        return {1: stage1_runner, 2: stage2_runner}

    monkeypatch.setattr(engine, "build_runners", fake_build_runners)
    run = _run(computed=["a", "b"])
    svc = _service(run, {})

    await svc.reset_from(run.analysis_id, 2, {"max_violations": 0})

    assert run.status == "failed"
    assert "2" not in run.stage_results  # downstream stayed cleared


# ---------------------------------------------------------------------------
# never-empty — edit S1 removing every compound is rejected (422), nothing persisted
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_edit_removing_all_compounds_is_rejected_and_persists_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_runners(monkeypatch)
    r1, r2 = uuid.uuid4(), uuid.uuid4()
    run = _run(computed=["a", "b"])
    run.stage_results["1"]["compounds"][0]["compound_id"] = str(r1)
    run.stage_results["1"]["compounds"][1]["compound_id"] = str(r2)
    run.stage_results["1"]["computed_ids"] = [str(r1), str(r2)]
    before_status = run.status
    svc = _service(run, {})
    repo = svc.analysis_repo

    # An edit may never empty a stage: removing the last remaining entity is rejected and
    # nothing is persisted (no status change, no clear, no S2 re-run).
    with pytest.raises(ValidationProblem) as e:
        await svc.edit_stage(run.analysis_id, 1, add=[], remove=[r1, r2])

    assert "least one compound" in (e.value.detail or "")
    assert run.status == before_status  # untouched
    assert run.stage_results["1"]["count"] == 2  # S1 set unchanged
    assert calls["2"] == []  # no S2 re-run
    assert repo.cleared == []  # nothing cleared


# ---------------------------------------------------------------------------
# reset-from is the explicit confirm: it RUNS even when parked at the edited stage,
# and clears the rerun_from marker.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reset_from_runs_and_clears_rerun_from(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_runners(monkeypatch)
    run = _run(computed=["a", "b"], mode="guided")
    run.status = "stage_1_awaiting_approval"
    run.current_stage = 1
    run.parameters["rerun_from"] = 1
    run.stage_results["2"]["stale"] = True
    svc = _service(run, {})

    # Explicit reset-from/1 (no overrides) is the confirm — it must RUN, not re-park.
    await svc.reset_from(run.analysis_id, 1, None)

    assert len(calls["2"]) == 1  # S2 actually re-ran
    assert "rerun_from" not in run.parameters  # confirm marker cleared


# ---------------------------------------------------------------------------
# cap — add beyond the compound cap -> 422 with the cap
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_edit_add_beyond_cap_is_422(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_runners(monkeypatch)
    cap = contracts.max_compounds()
    # Start with a full S1 set, then attempt to add one more.
    computed = [f"id-{i:05d}" for i in range(cap)]
    run = _run(computed=computed)
    new_id = uuid.uuid4()
    svc = _service(run, {new_id: "Extra"})
    with pytest.raises(ValidationProblem) as e:
        await svc.edit_stage(run.analysis_id, 1, add=[new_id], remove=[])
    assert str(cap) in (e.value.detail or "")


# ---------------------------------------------------------------------------
# stale guard — advance refused while any stage is stale
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_advance_refused_while_any_stage_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_runners(monkeypatch)
    run = _run(computed=["a", "b"], mode="guided")
    run.status = "stage_3_awaiting_approval"
    run.current_stage = 3
    run.stage_results["3"] = {"count": 1, "state": "computed"}
    run.stage_results["2"]["stale"] = True  # an upstream edit left S2 stale
    svc = _service(run, {})
    with pytest.raises(ConflictProblem):
        await svc.advance(run.analysis_id)


# ---------------------------------------------------------------------------
# F3 — dependency-closure run-set: a reset re-runs only the DAG closure, not
# "this stage + every later runnable stage". Proven over a monkeypatched
# RUNNABLE_STAGES spanning 1..8 (the Chunk-6 world where 7 and 8 are leaves).
# ---------------------------------------------------------------------------
def _multistage_run(mode: str = "auto") -> SimpleNamespace:
    """A settled run with stage_results 1..8 all computed, current_stage=8."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        mode=mode,
        status="complete",
        current_stage=8,
        parameters={},
        stage_results={str(i): {"count": 1, "state": "computed"} for i in range(1, 9)},
    )


def _recording_runners(called: list[int]) -> dict[int, object]:
    def make(stage: int):
        async def _runner(run: object) -> dict:
            called.append(stage)
            return {"count": 1, "state": "computed"}

        return _runner

    return {i: make(i) for i in range(1, 9)}


@pytest.mark.asyncio
async def test_reset_from_6_set_edit_reruns_only_7_not_8(monkeypatch):
    # Simulate the Chunk-6 world where 7 and 8 are runnable parallel leaves.
    monkeypatch.setattr(engine, "RUNNABLE_STAGES", (1, 2, 3, 4, 5, 6, 7, 8))
    monkeypatch.setattr(engine, "NEEDS_APPROVAL", frozenset())  # auto chain, no pause
    run = _multistage_run("auto")
    repo = FakeRepo(run)
    called: list[int] = []
    # set-edit path (param_overrides=None): downstream_closure(6) = {7}; 8 is NOT downstream of 6.
    run_set = await engine.reset_from(
        repo, run.id, 6, _recording_runners(called), param_overrides=None, defer=False
    )
    assert called == [7]  # S8 must NOT re-run (it depends on S5, not S6)
    assert repo.cleared == [{7}]  # only the closure was cleared
    assert run_set is None  # inline mode returns None


@pytest.mark.asyncio
async def test_reset_from_5_set_edit_reruns_full_downstream(monkeypatch):
    monkeypatch.setattr(engine, "RUNNABLE_STAGES", (1, 2, 3, 4, 5, 6, 7, 8))
    monkeypatch.setattr(engine, "NEEDS_APPROVAL", frozenset())
    run = _multistage_run("auto")
    repo = FakeRepo(run)
    called: list[int] = []
    await engine.reset_from(
        repo, run.id, 5, _recording_runners(called), param_overrides=None, defer=False
    )
    assert called == [6, 7, 8]  # closure(5) = {6,7,8}, all re-run, in order
    assert repo.cleared == [{6, 7, 8}]


@pytest.mark.asyncio
async def test_reset_from_defer_returns_run_set(monkeypatch):
    monkeypatch.setattr(engine, "RUNNABLE_STAGES", (1, 2, 3, 4, 5, 6, 7, 8))
    monkeypatch.setattr(engine, "NEEDS_APPROVAL", frozenset())
    run = _multistage_run("auto")
    repo = FakeRepo(run)
    run_set = await engine.reset_from(
        repo, run.id, 6, _recording_runners([]), param_overrides=None, defer=True
    )
    assert run_set == frozenset({7})  # the caller schedules exactly this set
    assert run.status == "stage_7_running"  # *_running committed at min(run_set)


# ---------------------------------------------------------------------------
# String/enum param overrides (ppi.network_type): validated as a string against its
# enum, not rejected by the numeric fallthrough ("must be a number").
# ---------------------------------------------------------------------------
def test_validate_overrides_accepts_enum_string_param() -> None:
    engine.validate_overrides("ppi", {"network_type": "physical"})  # valid enum member
    engine.validate_overrides("ppi", {"min_confidence": 0.7})  # numeric tier still fine


def test_validate_overrides_rejects_off_enum_string() -> None:
    with pytest.raises(ValidationProblem):
        engine.validate_overrides("ppi", {"network_type": "bogus"})


def test_validate_overrides_rejects_non_string_for_string_param() -> None:
    with pytest.raises(ValidationProblem):
        engine.validate_overrides("ppi", {"network_type": 123})


def test_validate_overrides_rejects_off_tier_numeric_enum() -> None:
    # min_confidence carries a numeric enum (STRING's confidence tiers). An in-range but
    # off-tier value (0.55 sits between the 0.15 and 0.9 bounds) must be rejected, symmetric
    # with the string-enum branch.
    with pytest.raises(ValidationProblem):
        engine.validate_overrides("ppi", {"min_confidence": 0.55})


def test_validate_overrides_accepts_on_tier_numeric_enum() -> None:
    for tier in (0.15, 0.4, 0.7, 0.9):
        engine.validate_overrides("ppi", {"min_confidence": tier})  # exact tier is valid


# ---------------------------------------------------------------------------
# Array param overrides (enrichment.sources): ADJUST-3
# ---------------------------------------------------------------------------
def test_validate_overrides_accepts_array_param() -> None:
    # enrichment.sources is an array of strings -> must validate, not 422.
    engine.validate_overrides("enrichment", {"sources": ["GO:BP", "KEGG"]})


def test_validate_overrides_rejects_non_array_for_array_param() -> None:
    with pytest.raises(ValidationProblem):
        engine.validate_overrides("enrichment", {"sources": "GO:BP"})


def test_validate_overrides_rejects_non_string_array_items() -> None:
    with pytest.raises(ValidationProblem):
        engine.validate_overrides("enrichment", {"sources": [1, 2]})


def test_sources_override_accepts_reac_wp() -> None:
    # REAC + WP are in the contract item enum -> valid override
    engine.validate_overrides("enrichment", {"sources": ["GO:BP", "REAC", "WP"]})


def test_sources_override_rejects_unknown_value() -> None:
    with pytest.raises(ValidationProblem):
        engine.validate_overrides("enrichment", {"sources": ["NOT_A_SOURCE"]})


# ---------------------------------------------------------------------------
# Terminal-leaf empty-gate exemption: ADJUST-4
# Stage 8 with count==0 (honest null) must COMPLETE, not park/fail.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stage8_zero_terms_completes_not_parked(monkeypatch) -> None:
    monkeypatch.setattr(engine, "RUNNABLE_STAGES", (8,))
    monkeypatch.setattr(engine, "NEEDS_APPROVAL", frozenset())  # auto chain
    run = SimpleNamespace(
        id=uuid.uuid4(),
        mode="auto",
        status="stage_8_running",
        current_stage=8,
        parameters={},
        stage_results={},
    )
    repo = FakeRepo(run)

    async def _s8(_run: Any) -> dict:
        return {"terms": [], "count": 0, "state": "computed", "flags": ["empty_input"]}

    await engine.execute_run(repo, run.id, {8: _s8})
    # Stage 8 with 0 terms is NOT empty-gated: the run completes rather than parking/failing.
    assert run.status == "complete"
    assert run.status != "stage_8_awaiting_approval"  # not parked as an empty stage
    assert run.status != "failed"
