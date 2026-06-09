import uuid

import pytest

from app.services.canonical import compound_id_from_key


@pytest.mark.asyncio
async def test_upsert_is_idempotent_on_canonical_key(session) -> None:
    from app.repositories.compound import CompoundRepository

    repo = CompoundRepository(session)
    key = "inchikey:LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    row = {
        "compound_id": uuid.UUID(compound_id_from_key(key)),
        "canonical_key": key,
        "canonical_name": "ethanol",
        "inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        "smiles": "CCO",
        "validation_status": "externally_validated",
    }
    await repo.upsert(row)
    await repo.upsert(row)  # second time is a no-op
    await session.commit()
    got = await repo.get_by_key(key)
    assert got is not None
    assert got.canonical_name == "ethanol"
    assert await repo.count() == 1


@pytest.mark.asyncio
async def test_manual_source_id_found(session) -> None:
    from app.repositories.compound import CompoundRepository

    repo = CompoundRepository(session)
    assert await repo.manual_source_id() is not None  # seeded by the migration
