import httpx
import pytest

from app.integrations.base import with_retry


@pytest.mark.asyncio
async def test_retries_then_succeeds() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return "ok"

    assert await with_retry(flaky, attempts=3, base_delay=0.0) == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_raises_after_exhausting_attempts() -> None:
    async def always_fail() -> str:
        raise httpx.ConnectError("boom")

    with pytest.raises(httpx.ConnectError):
        await with_retry(always_fail, attempts=2, base_delay=0.0)
