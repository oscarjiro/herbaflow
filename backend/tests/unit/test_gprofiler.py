"""Unit tests for integrations/gprofiler.py.

The g:Profiler client builds its own httpx.AsyncClient and POSTs a single
payload to /gost/profile/. These tests patch httpx.AsyncClient and bypass the
retry layer (with_retry) to assert payload construction and result parsing.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from integrations.gprofiler import run_enrichment


def _make_gprofiler_response(result_rows: list | None = None, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = {"result": result_rows or []}
    resp.raise_for_status.return_value = None
    return resp


def _make_mock_client(resp: MagicMock):
    """Return (context_manager, inner_client) so tests can inspect post() calls."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, mock_client


@pytest.mark.asyncio
async def test_run_enrichment_uses_benjamini_hochberg_correction():
    """g:Profiler payload must request Benjamini-Hochberg FDR correction
    (significance_threshold_method='fdr'), not the g:SCS default.

    Rationale: BH is the standard, reviewer-recognized multiple-testing
    correction reported across network-pharmacology literature, making our
    enrichment FDRs directly comparable to published reference studies.
    """
    resp = _make_gprofiler_response()
    cm, mock_client = _make_mock_client(resp)

    with patch("httpx.AsyncClient", return_value=cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.gprofiler.with_retry", side_effect=passthrough):
            await run_enrichment(["AKT1", "TNF", "IL6"])

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload.get("significance_threshold_method") == "fdr"
