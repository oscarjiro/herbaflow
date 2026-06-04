import httpx
import pytest
from integrations._retry import ServiceUnavailableError
from integrations.pubchem_bioassay import get_targets_by_inchikey


@pytest.mark.asyncio
async def test_get_targets_by_inchikey_raises_when_cid_lookup_unavailable(httpx_mock):
    # CID lookup returns 503 on every attempt → ServiceUnavailableError must
    # propagate instead of _get_cid returning None → [] targets.
    # with_retry default: max_retries=3 → 4 attempts consumed.
    for _ in range(4):
        httpx_mock.add_response(status_code=503)
    async with httpx.AsyncClient() as client:
        with pytest.raises(ServiceUnavailableError):
            await get_targets_by_inchikey(client, "BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
