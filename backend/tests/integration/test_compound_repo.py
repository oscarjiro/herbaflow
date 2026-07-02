import uuid

import pytest

from app.services.canonical import compound_id_from_key

# NOTE: test_manual_source_id_found removed — CompoundRepository.manual_source_id() was
# retired with the source_systems table (Wave 3 schema trim); there is nothing left to test.


@pytest.mark.asyncio
async def test_upsert_is_idempotent_on_compound_id(session) -> None:
    from app.repositories.compound import CompoundRepository

    repo = CompoundRepository(session)
    key = "inchikey:LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    cid = uuid.UUID(compound_id_from_key(key))
    row = {
        "compound_id": cid,
        "canonical_name": "ethanol",
        "inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        "smiles": "CCO",
        "validation_status": "externally_validated",
    }
    await repo.upsert(row)
    await repo.upsert(row)  # second time is a no-op (conflict on compound_id)
    await session.commit()
    got = await repo.get_by_id(cid)
    assert got is not None
    assert got.canonical_name == "ethanol"
    assert await repo.existing_ids([cid]) == {cid}
