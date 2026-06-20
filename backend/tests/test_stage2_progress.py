"""Stage 2 emits per-compound progress to the injected reporter."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.pipeline.stages import stage2


class _FakeReporter:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, int]] = []

    async def update(self, stage, processed, total) -> None:
        self.calls.append((stage, processed, total))


def _compound(name: str):
    # skip_adme path: no descriptors needed, every compound passes.
    return SimpleNamespace(compound_id=uuid.uuid4(), canonical_name=name)


@pytest.mark.asyncio
async def test_screen_reports_progress_per_compound() -> None:
    reporter = _FakeReporter()
    compounds = [_compound("A"), _compound("B"), _compound("C")]
    params = {
        "skip_adme": True,
        "apply_np_exception": False,
        "np_exception_threshold": 0.0,
        "apply_veber": False,
        "max_mw": 500.0,
        "max_logp": 5.0,
        "max_hbd": 5,
        "max_hba": 10,
        "max_tpsa": 140.0,
        "max_rotatable_bonds": 10,
        "max_violations": 1,
    }
    await stage2.screen(compounds, params, persist=None, reporter=reporter)
    # total is always the input size; processed climbs to the total.
    assert all(total == 3 for (_stage, _p, total) in reporter.calls)
    assert all(stage == 2 for (stage, _p, _t) in reporter.calls)
    assert reporter.calls[-1] == (2, 3, 3)
    assert [p for (_s, p, _t) in reporter.calls] == [1, 2, 3]
