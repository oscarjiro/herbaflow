"""Unit tests for the recent-runs list (service + schema layer).

TDD red → green path:
- Seed 3 runs with distinct created_at; assert newest-first ordering.
- Assert limit / offset paging.
- Assert the serialized AnalysisListItem has no stage_results key but DOES carry
  parameters with input_modes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.schemas.analysis import AnalysisListItem
from app.services.analysis import AnalysisService

# ---------------------------------------------------------------------------
# Fake repo that stores a list of runs and honours limit/offset/order
# ---------------------------------------------------------------------------


def _make_run(
    *,
    created_at: datetime,
    status: str = "complete",
    current_stage: int | None = 8,
    parameters: dict[str, Any] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        analysis_id=uuid.uuid4(),
        analysis_name="test",
        status=status,
        current_stage=current_stage,
        created_at=created_at,
        completed_at=created_at + timedelta(minutes=5),
        disease_id=uuid.uuid4(),
        parameters=parameters or {"input_modes": {"plant": "selection", "disease": "selection"}},
        stage_results={"1": {"count": 3}, "8": {"terms": []}},
        # extra ORM-like fields expected by AnalysisRead but not by AnalysisListItem
        mode="guided",
        expires_at=None,
        error_message=None,
    )


class FakeAnalysisRepoList:
    """Fake repo whose list_recent mirrors the real SELECT…ORDER BY…LIMIT…OFFSET."""

    def __init__(self, runs: list[SimpleNamespace]) -> None:
        # Store newest-first (mirrors ORDER BY created_at DESC)
        self._runs = sorted(runs, key=lambda r: r.created_at, reverse=True)
        self.session = None  # required by AnalysisService.__init__ (progress_repo wiring)

    async def list_recent(self, *, limit: int, offset: int) -> list[SimpleNamespace]:
        return self._runs[offset : offset + limit]


def _service_with_runs(runs: list[SimpleNamespace]) -> AnalysisService:
    svc = AnalysisService(
        plant_repo=None,
        disease_repo=None,
        analysis_repo=FakeAnalysisRepoList(runs),
        compound_repo=None,
    )
    return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

NOW = datetime(2026, 6, 19, 10, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_list_recent_newest_first() -> None:
    """Three runs returned newest-first."""
    r1 = _make_run(created_at=NOW - timedelta(hours=2))
    r2 = _make_run(created_at=NOW - timedelta(hours=1))
    r3 = _make_run(created_at=NOW)
    svc = _service_with_runs([r1, r2, r3])

    items = await svc.list_recent(limit=10, offset=0)

    assert len(items) == 3
    assert items[0].analysis_id == r3.analysis_id
    assert items[1].analysis_id == r2.analysis_id
    assert items[2].analysis_id == r1.analysis_id


@pytest.mark.asyncio
async def test_list_recent_limit() -> None:
    """limit=2 returns only the 2 newest."""
    r1 = _make_run(created_at=NOW - timedelta(hours=2))
    r2 = _make_run(created_at=NOW - timedelta(hours=1))
    r3 = _make_run(created_at=NOW)
    svc = _service_with_runs([r1, r2, r3])

    items = await svc.list_recent(limit=2, offset=0)

    assert len(items) == 2
    assert items[0].analysis_id == r3.analysis_id
    assert items[1].analysis_id == r2.analysis_id


@pytest.mark.asyncio
async def test_list_recent_offset() -> None:
    """offset=1 skips the newest run."""
    r1 = _make_run(created_at=NOW - timedelta(hours=2))
    r2 = _make_run(created_at=NOW - timedelta(hours=1))
    r3 = _make_run(created_at=NOW)
    svc = _service_with_runs([r1, r2, r3])

    items = await svc.list_recent(limit=10, offset=1)

    assert len(items) == 2
    assert items[0].analysis_id == r2.analysis_id
    assert items[1].analysis_id == r1.analysis_id


@pytest.mark.asyncio
async def test_list_recent_empty() -> None:
    """Empty repo returns an empty list (200, not an error)."""
    svc = _service_with_runs([])
    items = await svc.list_recent(limit=50, offset=0)
    assert items == []


def test_analysis_list_item_no_stage_results() -> None:
    """Serialized AnalysisListItem must not contain a stage_results key."""
    run = _make_run(
        created_at=NOW,
        parameters={"input_modes": {"plant": "selection", "disease": "selection"}},
    )
    item = AnalysisListItem.model_validate(run)
    dumped = item.model_dump()
    assert "stage_results" not in dumped


def test_analysis_list_item_carries_parameters_with_input_modes() -> None:
    """Serialized AnalysisListItem carries parameters including input_modes."""
    run = _make_run(
        created_at=NOW,
        parameters={
            "input_modes": {"plant": "selection", "disease": "selection"},
            "plant_ids": ["00000000-0000-0000-0000-000000000001"],
        },
    )
    item = AnalysisListItem.model_validate(run)
    assert item.parameters.get("input_modes") == {"plant": "selection", "disease": "selection"}
    assert "plant_ids" in item.parameters
