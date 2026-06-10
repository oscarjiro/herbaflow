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
        },
        stage_results={
            "1": _stage1_fragment(computed),
            "2": {"count": len(computed), "passed": [], "filtered": [], "state": "computed"},
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
    calls: dict[str, list] = {"1": [], "2": [], "3": [], "4": []}

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
                "targets": [{"target_id": "t0", "canonical_name": "T0"}],
                "disease_targets": [],
                "count": 1,
                "min_score_applied": 0.3,
                "state": "computed",
            }

        return {1: stage1_runner, 2: stage2_runner, 3: stage3_runner, 4: stage4_runner}

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

    assert {2} in repo.cleared
    assert len(calls["2"]) == 1  # re-ran stage 2
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
