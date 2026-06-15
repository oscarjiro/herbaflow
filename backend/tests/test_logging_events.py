# backend/tests/test_logging_events.py
import logging
import uuid

import pytest

from app.errors import NotFoundProblem
from app.services.analysis import AnalysisService


class _Repo:
    async def get(self, analysis_id):
        return None


@pytest.mark.asyncio
async def test_delete_missing_logs_nothing_sensitive_but_raises(caplog) -> None:
    svc = AnalysisService(
        plant_repo=None,
        disease_repo=None,
        analysis_repo=_Repo(),
        compound_repo=None,
        target_repo=None,
        compound_target_repo=None,
    )
    with pytest.raises(NotFoundProblem):
        await svc.delete(uuid.uuid4())


def test_logging_namespace_is_herbaflow() -> None:
    # The single logging home: every app logger is a child of "herbaflow".
    assert logging.getLogger("herbaflow.analysis").name.startswith("herbaflow")
