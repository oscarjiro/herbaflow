"""Run-status vocabulary helpers, validated against the shared contract."""

from __future__ import annotations

from app import contracts

PENDING = "pending"
COMPLETE = "complete"
FAILED = "failed"


def stage_status(stage: int, phase: str) -> str:
    """Compose a composite 'stage_{N}_{phase}' status; phase must be in the contract."""
    if phase not in contracts.stage_phases():
        raise ValueError(f"unknown stage phase: {phase}")
    return f"stage_{stage}_{phase}"


def is_terminal(status: str | None) -> bool:
    """True when the run has reached a terminal flat status."""
    return status in {COMPLETE, FAILED}


def is_settled(status: str | None) -> bool:
    """True when the run is not actively running: terminal or paused for approval."""
    return status in {COMPLETE, FAILED} or bool(status and status.endswith("_awaiting_approval"))


def stranded_statuses() -> list[str]:
    """Statuses that indicate a run was in-flight when the server process died.

    Returns ``["pending"] + ["stage_N_running" for every pipeline stage]``.  These are
    the only statuses that can never be reached again on a fresh process start, so a
    startup sweep can safely mark every run in one of these statuses as failed.

    Derived from the contract vocabulary via ``contracts.pipeline_stages()`` and
    ``stage_status()`` — no hardcoded stage numbers here.
    """
    return [PENDING] + [stage_status(n, "running") for n in contracts.pipeline_stages()]
