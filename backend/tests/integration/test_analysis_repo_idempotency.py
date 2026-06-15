# backend/tests/integration/test_analysis_repo_idempotency.py
import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.analysis import AnalysisRepository


async def _new(repo: AnalysisRepository, key: str | None):
    return await repo.create(
        analysis_name=None, disease_id=None, plant_ids=[], mode="auto", idempotency_key=key
    )


async def test_get_by_idempotency_key_roundtrip(session) -> None:
    repo = AnalysisRepository(session)
    run = await _new(repo, "key-abc")
    await session.commit()
    found = await repo.get_by_idempotency_key("key-abc")
    assert found is not None and found.analysis_id == run.analysis_id
    assert await repo.get_by_idempotency_key("key-missing") is None


async def test_duplicate_key_raises_integrity_error(session) -> None:
    repo = AnalysisRepository(session)
    await _new(repo, "key-dup")
    await session.commit()
    with pytest.raises(IntegrityError):
        await _new(repo, "key-dup")
