"""Stage 3 compute() emits climbing progress as compound coroutines complete."""

from __future__ import annotations

import pytest

from app.pipeline.stages import stage3


class _FakeReporter:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, int]] = []

    async def update(self, stage, processed, total) -> None:
        self.calls.append((stage, processed, total))


class _Chembl:
    async def targets_for_inchikey(self, ik, *, min_pchembl, min_confidence, connectivity_key=None):
        return []


class _Pubchem:
    async def active_targets_for_inchikey(self, ik):
        return []


@pytest.mark.asyncio
async def test_compute_reports_progress_to_total() -> None:
    reporter = _FakeReporter()

    async def _resolve(acc):
        return None

    compounds = [
        {"compound_id": "00000000-0000-0000-0000-000000000001", "inchi_key": "IK1"},
        {"compound_id": "00000000-0000-0000-0000-000000000002", "inchi_key": "IK2"},
    ]
    await stage3.compute(
        compounds,
        _Chembl(),
        _Pubchem(),
        resolve_target=_resolve,
        min_pchembl=5.0,
        min_confidence=7,
        reporter=reporter,
        progress_base=1,  # pretend 1 compound was reused
        progress_total=3,  # 1 reused + 2 fetched
    )
    assert all(stage == 3 and total == 3 for (stage, _p, total) in reporter.calls)
    # processed climbs from base+1 up to base+len(to_fetch) == total
    assert max(p for (_s, p, _t) in reporter.calls) == 3
