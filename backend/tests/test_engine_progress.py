"""build_runners forwards the reporter to the stage-2 and stage-3 runners."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.pipeline import engine
from app.pipeline.stages import stage2, stage3


@pytest.mark.asyncio
async def test_build_runners_forwards_reporter(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake_stage2_run(session, compounds, params, *, reporter=None):
        seen["stage2_reporter"] = reporter
        return {"passed": [], "filtered": [], "annotations": {}, "count": 0, "state": "computed"}

    async def fake_stage3_run(session, passed, params, *, reporter=None, **kw):
        seen["stage3_reporter"] = reporter
        return {
            "targets": [],
            "compound_targets": [],
            "per_compound": {},
            "coverage_pct": 0.0,
            "count": 0,
            "state": "computed",
        }

    monkeypatch.setattr(stage2, "run", fake_stage2_run)
    monkeypatch.setattr(stage3, "run", fake_stage3_run)

    sentinel = object()
    runners = engine.build_runners(session=None, reporter=sentinel)

    run = SimpleNamespace(
        parameters={"adme": {}, "target": {}},
        stage_results={"1": {"compounds": []}, "2": {"passed": []}},
    )
    await runners[2](run)
    await runners[3](run)
    assert seen["stage2_reporter"] is sentinel
    assert seen["stage3_reporter"] is sentinel
