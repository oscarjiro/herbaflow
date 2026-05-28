"""Unit tests for integrations/open_targets.py.

The integration creates its own httpx.AsyncClient internally, so we patch
`httpx.AsyncClient` to inject a mock client. The retry layer (with_retry)
is also patched to bypass sleep delays in tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from integrations.open_targets import get_disease_targets, OtAssociation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ot_response(rows: list[dict], status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response for the Open Targets GraphQL endpoint."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = {
        "data": {
            "disease": {
                "associatedTargets": {
                    "rows": rows
                }
            }
        }
    }
    if status_code >= 500:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _make_row(symbol: str, ensembl_id: str, score: float) -> dict:
    return {
        "target": {"approvedSymbol": symbol, "id": ensembl_id},
        "score": score,
    }


def _make_mock_client(resp: MagicMock) -> MagicMock:
    """Return a mock httpx.AsyncClient usable as an async context manager."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=resp)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# test_get_disease_targets_returns_parsed_results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_disease_targets_returns_parsed_results():
    """A successful response is parsed into a list of OtAssociation objects."""
    rows = [
        _make_row("AKT1", "ENSG00000142208", 0.85),
        _make_row("TP53", "ENSG00000141510", 0.72),
    ]
    resp = _make_ot_response(rows)
    mock_cm = _make_mock_client(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        # Bypass retry sleeps by patching with_retry to call fn directly
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.open_targets.with_retry", side_effect=passthrough):
            result = await get_disease_targets("EFO_0000400", min_score=0.3)

    assert len(result) == 2
    assert all(isinstance(r, OtAssociation) for r in result)
    gene_symbols = {r.gene_symbol for r in result}
    assert "AKT1" in gene_symbols
    assert "TP53" in gene_symbols
    assert result[0].ensembl_id in {"ENSG00000142208", "ENSG00000141510"}
    assert result[0].score > 0.0


# ---------------------------------------------------------------------------
# test_get_disease_targets_handles_empty_response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_disease_targets_handles_empty_response():
    """When the disease has no associatedTargets rows, return empty list."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"data": {}}
    resp.raise_for_status.return_value = None

    mock_cm = _make_mock_client(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.open_targets.with_retry", side_effect=passthrough):
            result = await get_disease_targets("EFO_0000000", min_score=0.3)

    assert result == []


@pytest.mark.asyncio
async def test_get_disease_targets_disease_none_returns_empty():
    """When disease key is None/absent in response, return empty list."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"data": {"disease": None}}
    resp.raise_for_status.return_value = None

    mock_cm = _make_mock_client(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.open_targets.with_retry", side_effect=passthrough):
            result = await get_disease_targets("EFO_0000001", min_score=0.3)

    assert result == []


# ---------------------------------------------------------------------------
# test_get_disease_targets_score_threshold_applied
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_disease_targets_score_threshold_applied():
    """Associations below min_score are excluded from the returned list."""
    rows = [
        _make_row("AKT1", "ENSG00000142208", 0.80),   # above threshold
        _make_row("CASP3", "ENSG00000164305", 0.20),  # below threshold → excluded
        _make_row("TP53", "ENSG00000141510", 0.50),   # above threshold
    ]
    resp = _make_ot_response(rows)
    mock_cm = _make_mock_client(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.open_targets.with_retry", side_effect=passthrough):
            result = await get_disease_targets("EFO_0000400", min_score=0.4)

    assert len(result) == 2
    gene_symbols = {r.gene_symbol for r in result}
    assert "AKT1" in gene_symbols
    assert "TP53" in gene_symbols
    assert "CASP3" not in gene_symbols


@pytest.mark.asyncio
async def test_get_disease_targets_all_below_threshold_returns_empty():
    """When every row is below the threshold, return an empty list."""
    rows = [
        _make_row("AKT1", "ENSG00000142208", 0.10),
        _make_row("TP53", "ENSG00000141510", 0.05),
    ]
    resp = _make_ot_response(rows)
    mock_cm = _make_mock_client(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.open_targets.with_retry", side_effect=passthrough):
            result = await get_disease_targets("EFO_0000400", min_score=0.3)

    assert result == []


# ---------------------------------------------------------------------------
# test_get_disease_targets_handles_http_error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_disease_targets_handles_http_error_returns_empty():
    """HTTP errors (5xx after retries) are caught and return an empty list."""
    from integrations._retry import ServiceUnavailableError

    with patch("httpx.AsyncClient"):
        with patch(
            "integrations.open_targets.with_retry",
            side_effect=ServiceUnavailableError("Open Targets", last_status=503),
        ):
            result = await get_disease_targets("EFO_0000400", min_score=0.3)

    assert result == []


@pytest.mark.asyncio
async def test_get_disease_targets_handles_generic_http_error_returns_empty():
    """Generic httpx.HTTPError is caught and returns an empty list."""
    with patch("httpx.AsyncClient"):
        with patch(
            "integrations.open_targets.with_retry",
            side_effect=httpx.ConnectError("connection refused"),
        ):
            result = await get_disease_targets("EFO_0000400", min_score=0.3)

    # ConnectError is a subclass of httpx.HTTPError → caught by the handler
    assert result == []
