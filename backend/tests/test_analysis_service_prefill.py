import uuid
from types import SimpleNamespace

import pytest

from app.services.analysis import AnalysisService


class _StubCompoundRepo:
    def __init__(self, names: dict[uuid.UUID, str]) -> None:
        self._names = names

    async def get_many(self, ids: list[uuid.UUID]):
        return [SimpleNamespace(compound_id=i, canonical_name=self._names[i]) for i in ids]


@pytest.mark.asyncio
async def test_prefill_compound_stage_carries_canonical_name() -> None:
    cid = uuid.uuid4()
    svc = AnalysisService(
        plant_repo=None,
        disease_repo=None,
        analysis_repo=None,
        compound_repo=_StubCompoundRepo({cid: "curcumin"}),
    )
    stage_edits: dict = {}
    stage_results: dict = {}

    await svc._prefill_compound_stage(1, [cid], stage_edits, stage_results)

    compounds = stage_results["1"]["compounds"]
    assert compounds[0]["compound_id"] == str(cid)
    assert compounds[0]["canonical_name"] == "curcumin"
