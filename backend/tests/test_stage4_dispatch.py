"""Stage 4 registration: guided checkpoint at S4; an empty side parks (Approve refused),
it does not fail.

Reuses ``FakeRepo`` from ``tests.test_engine`` (its method set — get/set_status/
set_stage_result/complete/fail — is exactly what the inline dispatch path here needs).
``test_engine`` exposes no ``make_run`` with the (mode/current_stage/status) signature the
plan sketched, so the run double is built inline as a ``SimpleNamespace`` rather than
introducing a parallel fake-run factory.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.pipeline import engine
from tests.test_engine import FakeRepo


def _runners(s4_result: dict) -> dict[int, object]:
    async def r1(run: object) -> dict:
        return {
            "compounds": [{"compound_id": str(uuid.uuid4()), "canonical_name": "c"}],
            "count": 1,
        }

    async def r2(run: object) -> dict:
        return {"passed": [], "count": 1}

    async def r3(run: object) -> dict:
        return {
            "targets": [],
            "compound_targets": [],
            "per_compound": {},
            "coverage_pct": 0.0,
            "count": 0,
            "state": "computed",
        }

    async def r4(run: object) -> dict:
        return s4_result

    return {1: r1, 2: r2, 3: r3, 4: r4}


def _awaiting_s3_run() -> SimpleNamespace:
    """A guided run paused at the S3 checkpoint, ready for the advance into S4."""
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        mode="guided",
        status="stage_3_awaiting_approval",
        current_stage=3,
        error_message=None,
        disease_id=uuid.uuid4(),
        parameters={"stage_edits": {}, "disease_targets": {"min_score": 0.3}},
        stage_results={
            "1": {"count": 1},
            "2": {"count": 1, "passed": []},
            "3": {"count": 1, "targets": [{"target_id": "t0", "canonical_name": "T0"}]},
        },
    )


def test_stage4_is_registered() -> None:
    assert 4 in engine.RUNNABLE_STAGES
    assert 4 in engine.NEEDS_APPROVAL
    assert engine.STAGE_PARAM_GROUP[4] == "disease_targets"


@pytest.mark.asyncio
async def test_stage4_empty_side_proceeds_to_awaiting_not_failed() -> None:
    run = _awaiting_s3_run()
    repo = FakeRepo(run)
    empty_s4 = {
        "targets": [],
        "disease_targets": [],
        "count": 0,
        "min_score_applied": 0.9,
        "state": "computed",
    }
    runners = _runners(empty_s4)
    start = await engine.advance_run(repo, run.analysis_id, runners, defer=False)
    assert start is None
    # Empty side parks at the checkpoint (honesty flag); it does NOT fail (guided).
    assert run.status == "stage_4_awaiting_approval"
    assert run.stage_results["4"]["count"] == 0
    # But the empty checkpoint refuses Approve & Continue.
    from app.errors import ConflictProblem

    with pytest.raises(ConflictProblem):
        await engine.advance_run(repo, run.analysis_id, runners, defer=False)
