import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.compound_cache import _do_cache


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

    await _do_cache(
        [
            {
                "compound_id": "7373585f-6e71-532a-8e3e-330defb8fbe8",
                "canonical_key": "inchi::REFJWTPEDVJJIY-UHFFFAOYSA-N",
                "canonical_name": "quercetin",
                "pubchem_cid": "5280343",
                "inchikey": "REFJWTPEDVJJIY-UHFFFAOYSA-N",
            }
        ],
        session,
    )

    assert len(added) == 1
    assert added[0].canonical_key == "inchi::REFJWTPEDVJJIY-UHFFFAOYSA-N"
