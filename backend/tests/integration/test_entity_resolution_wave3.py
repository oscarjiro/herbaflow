import uuid

import pytest

from app.repositories.compound import CompoundRepository
from app.services.canonical import compound_id


@pytest.mark.asyncio
async def test_compound_upsert_and_lookup_by_derived_pk(session):
    cand = {"inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"}
    cid = uuid.UUID(compound_id(cand))
    repo = CompoundRepository(session)
    await repo.upsert(
        {
            "compound_id": cid,
            "inchi_key": cand["inchi_key"],
            "canonical_name": "ethanol",
            "is_pains_positive": False,
            "validation_status": "externally_validated",
        }
    )
    await session.flush()
    got = await repo.get_by_id(cid)
    assert got is not None and got.inchi_key == cand["inchi_key"]
