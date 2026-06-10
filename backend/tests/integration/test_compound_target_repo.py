import uuid

import pytest
from sqlalchemy import select

from app.models.compound_target import CompoundTarget
from app.repositories.compound_target import CompoundTargetRepository


@pytest.mark.asyncio
async def test_measured_upsert_then_overwrite(session, seed_compound, seed_target):
    repo = CompoundTargetRepository(session)
    cid, tid = seed_compound, seed_target
    base = {"compound_target_id": uuid.uuid4(), "compound_id": cid, "target_id": tid}
    await repo.upsert_measured(
        {**base, "prediction_method": "pubchem_bioassay", "pchembl_value": None}
    )
    await repo.upsert_measured(
        {**base, "prediction_method": "chembl_bioactivity", "pchembl_value": 6.5}
    )
    await session.flush()
    row = (
        await session.execute(
            select(CompoundTarget).where(
                CompoundTarget.compound_id == cid, CompoundTarget.target_id == tid
            )
        )
    ).scalar_one()
    assert row.prediction_method == "chembl_bioactivity"
    assert row.pchembl_value == 6.5


@pytest.mark.asyncio
async def test_targets_for_compound_lists_measured_edges(session, seed_compound, seed_target):
    repo = CompoundTargetRepository(session)
    cid, tid = seed_compound, seed_target
    await repo.upsert_measured(
        {
            "compound_target_id": uuid.uuid4(),
            "compound_id": cid,
            "target_id": tid,
            "prediction_method": "chembl_bioactivity",
            "pchembl_value": 6.5,
        }
    )
    await session.flush()
    assert await repo.targets_for_compound(cid) == [tid]
