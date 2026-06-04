import httpx
import pytest
from integrations._retry import ServiceUnavailableError, with_retry


@pytest.mark.asyncio
async def test_retry_succeeds_after_429():
    """Should retry up to 3 times on 429 and return success."""
    call_count = 0

    async def flaky_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            mock_response = httpx.Response(429)
            raise httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=httpx.Request("GET", "http://test"),
                response=mock_response,
            )
        return {"result": "ok"}

    result = await with_retry(flaky_call, max_retries=3, base_delay=0.01)
    assert result == {"result": "ok"}
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_raises_after_max_retries():
    """Should raise ServiceUnavailableError after max retries exhausted."""

    async def always_fails():
        raise httpx.HTTPStatusError(
            "429",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(429),
        )

    with pytest.raises(ServiceUnavailableError):
        await with_retry(always_fails, max_retries=3, base_delay=0.01)


@pytest.mark.asyncio
async def test_no_retry_on_400():
    """Should NOT retry on 4xx errors other than 429."""
    call_count = 0

    async def bad_request():
        nonlocal call_count
        call_count += 1
        raise httpx.HTTPStatusError(
            "400",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(400),
        )

    with pytest.raises(httpx.HTTPStatusError):
        await with_retry(bad_request, max_retries=3, base_delay=0.01)
    assert call_count == 1  # no retry


@pytest.mark.asyncio
async def test_retry_on_500():
    """Should retry on 5xx server errors."""
    call_count = 0

    async def server_error():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.HTTPStatusError(
                "503",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(503),
            )
        return "ok"

    result = await with_retry(server_error, max_retries=3, base_delay=0.01)
    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_service_unavailable_error_attributes():
    """ServiceUnavailableError should expose service and last_status."""

    async def always_fails():
        raise httpx.HTTPStatusError(
            "503",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(503),
        )

    with pytest.raises(ServiceUnavailableError) as exc_info:
        await with_retry(always_fails, max_retries=1, base_delay=0.01, service_name="TestService")

    err = exc_info.value
    assert err.service == "TestService"
    assert "TestService" in str(err)


@pytest.mark.asyncio
async def test_no_retry_on_404():
    """Should NOT retry on 404 (non-retriable 4xx)."""
    call_count = 0

    async def not_found():
        nonlocal call_count
        call_count += 1
        raise httpx.HTTPStatusError(
            "404",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(404),
        )

    with pytest.raises(httpx.HTTPStatusError):
        await with_retry(not_found, max_retries=3, base_delay=0.01)
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_on_502():
    """Should retry on 502 Bad Gateway."""
    call_count = 0

    async def bad_gateway():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.HTTPStatusError(
                "502",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(502),
            )
        return "recovered"

    result = await with_retry(bad_gateway, max_retries=3, base_delay=0.01)
    assert result == "recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_succeeds_on_first_attempt():
    """Should return immediately on first success without any retry."""
    call_count = 0

    async def instant_success():
        nonlocal call_count
        call_count += 1
        return "data"

    result = await with_retry(instant_success, max_retries=3, base_delay=0.01)
    assert result == "data"
    assert call_count == 1
