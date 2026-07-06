import uuid
from types import SimpleNamespace

import pytest

from app.errors import ConflictProblem
from app.pipeline import engine
from app.pipeline.stages import stage5


class FakeRepo:
    def __init__(self, run):
        self.run = run

    async def get(self, analysis_id):
        return self.run

    async def set_status(self, run, status, *, current_stage=None):
        run.status = status
        if current_stage is not None:
            run.current_stage = current_stage

    async def set_stage_result(self, run, stage, result):
        run.stage_results[str(stage)] = result

    async def complete(self, run):
        run.status = "complete"

    async def fail(self, run, message):
        run.status = "failed"
        run.error_message = message

    async def commit(self) -> None:
        pass


def _run(mode):
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        mode=mode,
        status="pending",
        current_stage=None,
        stage_results={},
        error_message=None,
        parameters={"plant_ids": [str(uuid.uuid4())]},
    )


def _compounds(n):
    return [{"compound_id": f"c{i}", "canonical_name": f"C{i}"} for i in range(n)]


def _targets(n):
    return [{"target_id": f"t{i}", "canonical_name": f"T{i}"} for i in range(n)]


def _runners(stage1_count, stage2_count, stage3_count=1, stage4_count=1):
    async def stage1_runner(r):
        return {
            "count": stage1_count,
            "compounds": _compounds(stage1_count),
            "per_plant": {},
            "state": "computed",
        }

    async def stage2_runner(r):
        return {
            "count": stage2_count,
            "passed": [],
            "filtered": [],
            "annotations": {},
            "state": "computed",
        }

    async def stage3_runner(r):
        return {
            "targets": _targets(stage3_count),
            "compound_targets": [],
            "per_compound": {},
            "coverage_pct": 0.0,
            "count": stage3_count,
            "state": "computed",
        }

    async def stage4_runner(r):
        return {
            "targets": _targets(stage4_count),
            "count": stage4_count,
            "min_score_applied": 0.3,
            "state": "computed",
        }

    async def stage5_runner(r):
        return await stage5.run(None, r)

    async def stage6_runner(r):
        # Engine-dispatch fake: a ready-made computed PPI result (no STRING call).
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

    async def stage7_runner(r):
        # Hub-ranking fake: one hub from the stage-6 node (no networkx call needed).
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

    async def stage8_runner(r):
        # Enrichment fake: honest null (empty overlap) — valid terminal completion.
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


@pytest.mark.asyncio
async def test_auto_runs_to_complete() -> None:
    run = _run("auto")
    repo = FakeRepo(run)

    await engine.execute_run(repo, run.analysis_id, _runners(2, 1))

    assert run.status == "complete"
    assert run.stage_results["1"]["count"] == 2


@pytest.mark.asyncio
async def test_guided_pauses_for_approval() -> None:
    run = _run("guided")
    repo = FakeRepo(run)
    runners = _runners(1, 1)

    await engine.execute_run(repo, run.analysis_id, runners)
    assert run.status == "stage_1_awaiting_approval"

    # Approving stage 1 runs stage 2, which (guided) pauses again.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_2_awaiting_approval"

    # Approving stage 2 runs stage 3, which (guided) pauses at the S3 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_3_awaiting_approval"

    # Approving stage 3 runs stage 4, which (guided) pauses at the S4 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_4_awaiting_approval"

    # Approving stage 4 runs stage 5 (overlap), which (guided) pauses at the S5 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_5_awaiting_approval"

    # Approving stage 5 runs stage 6 (PPI), which (guided) pauses at the S6 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_6_awaiting_approval"

    # Approving stage 6 runs stage 7 (hub ranking), which (guided) pauses at the S7 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_7_awaiting_approval"

    # Approving stage 7 runs stage 8 (enrichment), which (guided) pauses at the S8 checkpoint.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_8_awaiting_approval"

    # Approving the last runnable stage completes the run.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "complete"


@pytest.mark.asyncio
async def test_auto_fails_on_empty_stage1() -> None:
    """Auto: an empty Stage 1 stores its count-0 result, then fails with the honesty note
    (the same addable-empty branch S2/S3/S4 use), so the user can add a compound and re-run."""
    run = _run("auto")
    repo = FakeRepo(run)

    await engine.execute_run(repo, run.analysis_id, _runners(0, 0))
    assert run.status == "failed"
    assert run.stage_results["1"]["count"] == 0
    assert "step 1" in run.error_message.lower()
    assert "compound" in run.error_message.lower()


@pytest.mark.asyncio
async def test_guided_parks_empty_stage1_then_refuses_advance() -> None:
    """Guided: an empty Stage 1 parks at its checkpoint with a stored count-0 result (not
    failed), so the frontend renders the add-a-compound shell; advance is refused."""
    run = _run("guided")
    repo = FakeRepo(run)
    runners = _runners(0, 0)

    await engine.execute_run(repo, run.analysis_id, runners)
    assert run.status == "stage_1_awaiting_approval"
    assert run.stage_results["1"]["count"] == 0

    # Approving an empty stage is refused (no results to carry forward).
    with pytest.raises(ConflictProblem):
        await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_1_awaiting_approval"  # unchanged


@pytest.mark.asyncio
async def test_advance_rejects_wrong_state() -> None:
    run = _run("guided")
    run.status = "stage_1_running"
    repo = FakeRepo(run)
    with pytest.raises(ConflictProblem):
        await engine.advance_run(repo, run.analysis_id, _runners(1, 1))


@pytest.mark.asyncio
async def test_auto_fails_on_empty_stage3() -> None:
    run = _run("auto")
    repo = FakeRepo(run)
    await engine.execute_run(repo, run.analysis_id, _runners(2, 2, stage3_count=0))
    assert run.status == "failed"
    assert "step 3" in run.error_message.lower()


@pytest.mark.asyncio
async def test_auto_fails_on_empty_stage4() -> None:
    run = _run("auto")
    repo = FakeRepo(run)
    await engine.execute_run(repo, run.analysis_id, _runners(2, 2, stage4_count=0))
    assert run.status == "failed"
    assert "step 4" in run.error_message.lower()


@pytest.mark.asyncio
async def test_guided_parks_empty_stage3_then_refuses_advance() -> None:
    run = _run("guided")
    repo = FakeRepo(run)
    runners = _runners(1, 1, stage3_count=0)

    await engine.execute_run(repo, run.analysis_id, runners)  # park S1
    await engine.advance_run(repo, run.analysis_id, runners)  # run S2, park S2
    await engine.advance_run(repo, run.analysis_id, runners)  # run S3 (0), park S3
    assert run.status == "stage_3_awaiting_approval"
    assert run.stage_results["3"]["count"] == 0

    # Approving an empty stage is refused.
    with pytest.raises(ConflictProblem):
        await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "stage_3_awaiting_approval"  # unchanged


# ---------------------------------------------------------------------------
# Stage 6 empty-network exemption (0-count PPI is an honest-null, not a failure)
# ---------------------------------------------------------------------------


def _runners_with_empty_stage6(stage1_count=2, stage2_count=2, stage3_count=1, stage4_count=1):
    """Like _runners() but Stage 6 returns 0 nodes and 0 edges (fully empty network)."""
    base = _runners(stage1_count, stage2_count, stage3_count, stage4_count)

    async def stage6_empty(r):
        return {
            "state": "computed",
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "count": 0,
            "flags": ["sparse_or_empty_network"],
        }

    return {**base, 6: stage6_empty}


# STR-1 (2026-07-06): STRING imposes no identifier cap; caps disabled, reversible — restore to
# re-enable. Stage 6 no longer emits a blocked-overflow marker and the engine's AD-6 blocked branch
# is commented out, so this helper + its two regression tests are disabled. Restore to re-enable.
#
# def _runners_with_blocked_stage6(stage1_count=2, stage2_count=2, stage3_count=1, stage4_count=1):
#     """Like _runners() but Stage 6 returns the blocked-overflow marker."""
#     base = _runners(stage1_count, stage2_count, stage3_count, stage4_count)
#
#     async def stage6_blocked(r):
#         return {
#             "blocked": True,
#             "reason": "overlap_too_large",
#             "overlap_count": 600,
#             "max_proteins": 400,
#         }
#
#     return {**base, 6: stage6_blocked}


@pytest.mark.asyncio
async def test_auto_completes_when_stage6_empty_network() -> None:
    """Auto run: valid Stage-5 overlap + 0-edge/0-node Stage-6 => complete (not failed)."""
    run = _run("auto")
    repo = FakeRepo(run)

    await engine.execute_run(repo, run.analysis_id, _runners_with_empty_stage6())

    assert run.status == "complete"
    assert run.stage_results["6"]["count"] == 0
    # Stages 7 and 8 still ran.
    assert "7" in run.stage_results
    assert "8" in run.stage_results


@pytest.mark.asyncio
async def test_guided_parks_stage6_empty_then_advance_succeeds() -> None:
    """Guided run: empty Stage-6 parks at S6 checkpoint; advance is NOT refused; run completes."""
    run = _run("guided")
    repo = FakeRepo(run)
    runners = _runners_with_empty_stage6()

    await engine.execute_run(repo, run.analysis_id, runners)  # park S1
    await engine.advance_run(repo, run.analysis_id, runners)  # run S2, park S2
    await engine.advance_run(repo, run.analysis_id, runners)  # run S3, park S3
    await engine.advance_run(repo, run.analysis_id, runners)  # run S4, park S4
    await engine.advance_run(repo, run.analysis_id, runners)  # run S5, park S5
    await engine.advance_run(repo, run.analysis_id, runners)  # run S6 (empty), park S6
    assert run.status == "stage_6_awaiting_approval"
    assert run.stage_results["6"]["count"] == 0

    # Approving an empty Stage 6 must NOT raise ConflictProblem (was the bug).
    await engine.advance_run(repo, run.analysis_id, runners)  # run S7, park S7
    assert run.status == "stage_7_awaiting_approval"

    await engine.advance_run(repo, run.analysis_id, runners)  # run S8, park S8
    assert run.status == "stage_8_awaiting_approval"

    await engine.advance_run(repo, run.analysis_id, runners)  # complete
    assert run.status == "complete"


def _runners_no_s5_overlap():
    """Runner set where S3 and S4 have disjoint target sets so Stage 5 produces 0 overlap."""
    base = _runners(2, 2, stage3_count=1, stage4_count=1)

    async def stage3_no_match(r):
        return {
            "targets": [{"target_id": "t_compound_only", "gene_symbol": "G1"}],
            "compound_targets": [],
            "per_compound": {},
            "coverage_pct": 0.0,
            "count": 1,
            "state": "computed",
        }

    async def stage4_no_match(r):
        return {
            "targets": [{"target_id": "t_disease_only", "gene_symbol": "G2"}],
            "count": 1,
            "min_score_applied": 0.3,
            "state": "computed",
        }

    return {**base, 3: stage3_no_match, 4: stage4_no_match}


@pytest.mark.asyncio
async def test_regression_stage5_zero_overlap_still_fails_auto() -> None:
    """Regression: Stage-5 producing 0 overlap is a terminal hard-stop in auto mode."""
    run = _run("auto")
    repo = FakeRepo(run)
    await engine.execute_run(repo, run.analysis_id, _runners_no_s5_overlap())
    assert run.status == "failed"
    assert "overlap" in run.error_message.lower() or "network" in run.error_message.lower()


@pytest.mark.asyncio
async def test_regression_stage5_zero_overlap_still_fails_guided() -> None:
    """Regression: Stage-5 producing 0 overlap is a terminal hard-stop in guided mode."""
    run = _run("guided")
    repo = FakeRepo(run)
    runners = _runners_no_s5_overlap()

    await engine.execute_run(repo, run.analysis_id, runners)  # park S1
    await engine.advance_run(repo, run.analysis_id, runners)  # park S2
    await engine.advance_run(repo, run.analysis_id, runners)  # park S3
    await engine.advance_run(repo, run.analysis_id, runners)  # park S4
    # Advance from S4 runs S5 which finds 0 overlap — terminal fail, even in guided mode.
    await engine.advance_run(repo, run.analysis_id, runners)
    assert run.status == "failed"
    assert "overlap" in run.error_message.lower() or "network" in run.error_message.lower()


# STR-1 (2026-07-06): STRING imposes no identifier cap; caps disabled, reversible — restore to
# re-enable. The Stage-6 blocked-overflow regressions (auto fail / guided park) are disabled because
# the stage no longer emits a blocked marker and the engine's AD-6 branch is commented out.
#
# @pytest.mark.asyncio
# async def test_regression_stage6_blocked_overflow_auto_fails() -> None:
#     """Regression: Stage-6 blocked (overflow) in auto mode still hard-fails."""
#     run = _run("auto")
#     repo = FakeRepo(run)
#
#     await engine.execute_run(repo, run.analysis_id, _runners_with_blocked_stage6())
#
#     assert run.status == "failed"
#     assert run.stage_results["6"].get("blocked") is True
#
#
# @pytest.mark.asyncio
# async def test_regression_stage6_blocked_overflow_guided_parks() -> None:
#     """Regression: Stage-6 blocked (overflow) in guided mode parks at S6 (not an error)."""
#     run = _run("guided")
#     repo = FakeRepo(run)
#     runners = _runners_with_blocked_stage6()
#
#     await engine.execute_run(repo, run.analysis_id, runners)  # park S1
#     await engine.advance_run(repo, run.analysis_id, runners)  # park S2
#     await engine.advance_run(repo, run.analysis_id, runners)  # park S3
#     await engine.advance_run(repo, run.analysis_id, runners)  # park S4
#     await engine.advance_run(repo, run.analysis_id, runners)  # park S5
#     await engine.advance_run(repo, run.analysis_id, runners)  # run S6 => blocked => park S6
#
#     assert run.status == "stage_6_awaiting_approval"
#     assert run.stage_results["6"].get("blocked") is True
