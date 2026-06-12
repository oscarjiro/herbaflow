"""Unit tests for the deferred background entrypoint ``run_stages_task``.

The background task owns its session and MUST mark the run ``failed`` if any stage
runner raises — otherwise a crash (e.g. a provider outage) leaves the run stuck in a
``*_running`` status forever. This guard covers the create path AND the four mutating
endpoints (advance / reset-from / edit), which all schedule this task.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.pipeline import engine
from app.pipeline.stages import stage5


class _FakeRepo:
    def __init__(self, run: SimpleNamespace) -> None:
        self.run = run

    async def get(self, analysis_id: uuid.UUID) -> SimpleNamespace:
        return self.run

    async def set_status(
        self, run: SimpleNamespace, status: str, *, current_stage: int | None = None
    ) -> None:
        run.status = status
        if current_stage is not None:
            run.current_stage = current_stage

    async def set_stage_result(self, run: SimpleNamespace, stage: int, result: dict) -> None:
        run.stage_results[str(stage)] = result

    async def complete(self, run: SimpleNamespace) -> None:
        run.status = "complete"

    async def fail(self, run: SimpleNamespace, message: str) -> None:
        run.status = "failed"
        run.error_message = message


def _run() -> SimpleNamespace:
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        mode="auto",
        status="stage_1_running",
        current_stage=1,
        stage_results={},
        error_message=None,
        parameters={},
    )


@pytest.mark.asyncio
async def test_run_stages_task_marks_failed_when_runner_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run()
    committed: list[bool] = []

    async def _commit() -> None:
        committed.append(True)

    fake_session = SimpleNamespace(commit=_commit)

    @asynccontextmanager
    async def fake_scope():
        yield fake_session

    async def boom(_run: SimpleNamespace) -> dict:
        raise RuntimeError("provider outage")

    monkeypatch.setattr(engine.db, "session_scope", fake_scope)
    monkeypatch.setattr(engine, "AnalysisRepository", lambda session: _FakeRepo(run))
    monkeypatch.setattr(engine, "build_runners", lambda session: {1: boom, 2: boom, 3: boom})

    await engine.run_stages_task(run.analysis_id, 1)

    assert run.status == "failed"
    assert "provider outage" in (run.error_message or "")
    assert committed == [True], "the failed mark must be committed"


@pytest.mark.asyncio
async def test_run_stages_task_completes_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run()

    async def _commit() -> None:
        return None

    fake_session = SimpleNamespace(commit=_commit)

    @asynccontextmanager
    async def fake_scope():
        yield fake_session

    async def stage1(_run: SimpleNamespace) -> dict:
        return {"count": 1, "compounds": [{"compound_id": "c0", "canonical_name": "C0"}]}

    async def stage2(_run: SimpleNamespace) -> dict:
        return {"count": 1, "passed": [], "filtered": [], "annotations": {}, "state": "computed"}

    async def stage3(_run: SimpleNamespace) -> dict:
        return {
            "targets": [{"target_id": "t0", "canonical_name": "T0"}],
            "compound_targets": [],
            "per_compound": {},
            "coverage_pct": 0.0,
            "count": 1,
            "state": "computed",
        }

    async def stage4(_run: SimpleNamespace) -> dict:
        return {
            "targets": [{"target_id": "t0", "canonical_name": "T0", "score": 0.5}],
            "count": 1,
            "min_score_applied": 0.3,
            "state": "computed",
        }

    async def stage5_runner(r: SimpleNamespace) -> dict:
        # S3/S4 both carry t0 -> overlap count 1 -> S5 succeeds and feeds S6.
        return await stage5.run(None, r)

    async def stage6(_run: SimpleNamespace) -> dict:
        # Ready-made computed PPI result (no STRING call).
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

    async def stage7(_run: SimpleNamespace) -> dict:
        # Hub-ranking fake: one hub -> the run continues to stage 8.
        return {
            "state": "computed",
            "hubs": [
                {
                    "rank": 1,
                    "gene_symbol": "G0",
                    "target_id": "t0",
                    "degree": 0.0,
                    "betweenness": 0.0,
                    "closeness": 0.0,
                    "eigenvector": 0.0,
                    "composite": 0.0,
                    "source_url": None,
                }
            ],
            "ranking_metric": "hub_bottleneck_composite",
            "composite_weight": 0.5,
            "normalization": "min_max",
            "node_count": 1,
            "top_n": 20,
            "count": 1,
            "flags": ["network_too_small"],
        }

    async def stage8(_run: SimpleNamespace) -> dict:
        # Enrichment fake: honest null — valid terminal completion.
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
            "fdr_threshold": 0.05,
            "min_term_size": 5,
            "sources": ["GO:BP"],
        }

    monkeypatch.setattr(engine.db, "session_scope", fake_scope)
    monkeypatch.setattr(engine, "AnalysisRepository", lambda session: _FakeRepo(run))
    monkeypatch.setattr(
        engine,
        "build_runners",
        lambda session: {
            1: stage1,
            2: stage2,
            3: stage3,
            4: stage4,
            5: stage5_runner,
            6: stage6,
            7: stage7,
            8: stage8,
        },
    )

    await engine.run_stages_task(run.analysis_id, 1)

    assert run.status == "complete"
