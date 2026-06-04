from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.compound_persist import _do_persist


class _FakeResult:
    def first(self):
        return None  # nothing cached yet


@pytest.mark.asyncio
async def test_cache_stores_inchi_canonical_key_not_pubchem():
    session = MagicMock()
    session.exec = AsyncMock(return_value=_FakeResult())
    session.add = MagicMock()
    session.commit = AsyncMock()

    added = []
    session.add.side_effect = lambda obj: added.append(obj)

    await _do_persist(
        [
            {
                "compound_id": "21d75a4d-8ff2-527e-876c-ba5ef28a68e8",
                "canonical_key": "inchikey:REFJWTPEDVJJIY-UHFFFAOYSA-N",
                "canonical_name": "quercetin",
                "pubchem_cid": "5280343",
                "inchikey": "REFJWTPEDVJJIY-UHFFFAOYSA-N",
            }
        ],
        session,
    )

    assert len(added) == 1
    assert added[0].canonical_key == "inchikey:REFJWTPEDVJJIY-UHFFFAOYSA-N"
