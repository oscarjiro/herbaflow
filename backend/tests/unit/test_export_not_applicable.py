import pytest
from uuid import UUID
from fastapi import HTTPException
from app.routers.analyses import export_stage_results


class _Run:
    analysis_name = "demo"
    stage_results = {"stage_1": {"state": "not_applicable"}}


class _Session:  # get_run is monkeypatched; session unused
    pass


@pytest.mark.asyncio
async def test_export_not_applicable_stage_returns_422(monkeypatch):
    from app.repositories import analysis_repo

    async def fake_get_run(session, analysis_id):
        return _Run()

    monkeypatch.setattr(analysis_repo, "get_run", fake_get_run)

    with pytest.raises(HTTPException) as exc:
        await export_stage_results(
            None,  # request placeholder (unused; rate limiter disabled in tests)
            UUID("00000000-0000-0000-0000-0000000000aa"),
            "1",
            format="csv",
            session=_Session(),
        )
    assert exc.value.status_code == 422
    assert "not applicable" in exc.value.detail.lower()
