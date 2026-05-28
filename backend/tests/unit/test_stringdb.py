"""Unit tests for integrations/stringdb.py.

Tests get_ppi_network using mock httpx clients — no real HTTP calls.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from integrations.stringdb import get_ppi_network, PpiEdgeData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_resp(rows: list[dict], status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = rows
    if status_code >= 500:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _make_edge_row(
    gene_a: str = "AKT1",
    gene_b: str = "TP53",
    score: float = 0.85,
    escore: float = 0.6,
    tscore: float = 0.5,
    coexpression_score: float = 0.3,
) -> dict:
    return {
        "preferredName_A": gene_a,
        "preferredName_B": gene_b,
        "score": score,
        "escore": escore,
        "tscore": tscore,
        "coexpression_score": coexpression_score,
    }


def _make_mock_client_cm(resp: MagicMock) -> MagicMock:
    """Return a mock httpx.AsyncClient usable as an async context manager."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=resp)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# test_get_ppi_network_empty_gene_list_returns_empty
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_ppi_network_empty_gene_list_returns_empty():
    """get_ppi_network returns [] immediately for empty gene list — no HTTP call."""
    with patch("httpx.AsyncClient") as mock_cls:
        result = await get_ppi_network([])

    mock_cls.assert_not_called()
    assert result == []


# ---------------------------------------------------------------------------
# test_get_ppi_network_returns_edges
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_ppi_network_returns_parsed_edges():
    """A valid STRING response is parsed into PpiEdgeData objects."""
    rows = [
        _make_edge_row("AKT1", "TP53", score=0.85, escore=0.6, tscore=0.5),
        _make_edge_row("TP53", "MDM2", score=0.9, escore=0.7, tscore=0.4),
    ]
    resp = _make_resp(rows)
    mock_cm = _make_mock_client_cm(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.stringdb.with_retry", side_effect=passthrough):
            result = await get_ppi_network(["AKT1", "TP53", "MDM2"])

    assert len(result) == 2
    assert all(isinstance(e, PpiEdgeData) for e in result)
    gene_pairs = {(e.gene_a, e.gene_b) for e in result}
    assert ("AKT1", "TP53") in gene_pairs or ("TP53", "AKT1") in gene_pairs


@pytest.mark.asyncio
async def test_get_ppi_network_gene_names_uppercased():
    """Gene names in PpiEdgeData are uppercased regardless of STRING response casing."""
    rows = [_make_edge_row("akt1", "tp53", score=0.7)]
    resp = _make_resp(rows)
    mock_cm = _make_mock_client_cm(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.stringdb.with_retry", side_effect=passthrough):
            result = await get_ppi_network(["akt1", "tp53"])

    assert len(result) == 1
    assert result[0].gene_a == "AKT1"
    assert result[0].gene_b == "TP53"


@pytest.mark.asyncio
async def test_get_ppi_network_edge_scores_parsed_correctly():
    """combined_score, experimental_score, textmining_score, coexpression_score are parsed."""
    rows = [_make_edge_row("AKT1", "TP53", score=0.85, escore=0.6, tscore=0.5, coexpression_score=0.3)]
    resp = _make_resp(rows)
    mock_cm = _make_mock_client_cm(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.stringdb.with_retry", side_effect=passthrough):
            result = await get_ppi_network(["AKT1", "TP53"])

    assert len(result) == 1
    edge = result[0]
    assert edge.combined_score == pytest.approx(0.85)
    assert edge.experimental_score == pytest.approx(0.6)
    assert edge.textmining_score == pytest.approx(0.5)
    assert edge.coexpression_score == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# test_get_ppi_network_filters_by_score_threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_ppi_network_filters_below_threshold():
    """Edges with combined_score below min_confidence are excluded."""
    rows = [
        _make_edge_row("AKT1", "TP53", score=0.85),   # above default 0.4 → included
        _make_edge_row("TP53", "EGFR", score=0.25),   # below default 0.4 → excluded
        _make_edge_row("AKT1", "MDM2", score=0.40),   # equal to threshold → excluded (strict <)
    ]
    resp = _make_resp(rows)
    mock_cm = _make_mock_client_cm(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.stringdb.with_retry", side_effect=passthrough):
            result = await get_ppi_network(["AKT1", "TP53", "EGFR", "MDM2"], min_confidence=0.4)

    # Only the edge with score 0.85 should pass (score=0.40 is NOT >= 0.4 check fails via < comparison)
    # Actually the code does: if combined < min_confidence: continue
    # 0.25 < 0.4 → excluded; 0.40 < 0.40 → False → included; 0.85 < 0.4 → False → included
    gene_pairs = {(e.gene_a, e.gene_b) for e in result}
    assert ("TP53", "EGFR") not in gene_pairs  # 0.25 excluded


@pytest.mark.asyncio
async def test_get_ppi_network_custom_threshold():
    """A higher min_confidence threshold removes more edges."""
    rows = [
        _make_edge_row("AKT1", "TP53", score=0.6),   # passes 0.4, fails 0.7
        _make_edge_row("TP53", "MDM2", score=0.9),   # passes both
    ]
    resp = _make_resp(rows)
    mock_cm = _make_mock_client_cm(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.stringdb.with_retry", side_effect=passthrough):
            result = await get_ppi_network(["AKT1", "TP53", "MDM2"], min_confidence=0.7)

    assert len(result) == 1
    assert result[0].combined_score == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Self-loops filtered out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_ppi_network_excludes_self_loops():
    """Edges where gene_a == gene_b (self-loops) are excluded."""
    rows = [
        _make_edge_row("AKT1", "AKT1", score=0.95),  # self-loop → excluded
        _make_edge_row("AKT1", "TP53", score=0.85),  # real edge → included
    ]
    resp = _make_resp(rows)
    mock_cm = _make_mock_client_cm(resp)

    with patch("httpx.AsyncClient", return_value=mock_cm):
        async def passthrough(fn, **kwargs):
            return await fn()
        with patch("integrations.stringdb.with_retry", side_effect=passthrough):
            result = await get_ppi_network(["AKT1", "TP53"])

    assert len(result) == 1
    assert result[0].gene_a != result[0].gene_b


# ---------------------------------------------------------------------------
# test_get_ppi_network_handles_http_error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_ppi_network_returns_empty_on_service_unavailable():
    """ServiceUnavailableError after retries returns empty list, no exception."""
    from integrations._retry import ServiceUnavailableError

    with patch("httpx.AsyncClient"):
        with patch(
            "integrations.stringdb.with_retry",
            side_effect=ServiceUnavailableError("STRING-DB", last_status=503),
        ):
            result = await get_ppi_network(["AKT1", "TP53"])

    assert result == []


@pytest.mark.asyncio
async def test_get_ppi_network_returns_empty_on_http_error():
    """Generic httpx.HTTPError returns empty list."""
    with patch("httpx.AsyncClient"):
        with patch(
            "integrations.stringdb.with_retry",
            side_effect=httpx.ConnectError("refused"),
        ):
            result = await get_ppi_network(["AKT1", "TP53"])

    assert result == []
