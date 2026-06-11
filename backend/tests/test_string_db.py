import httpx
import pytest

from app.errors import ServiceUnavailableError
from app.integrations.string_db import StringClient, StringEdge


@pytest.mark.asyncio
async def test_network_parses_edges(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json=[
                {
                    "preferredName_A": "AKT1",
                    "preferredName_B": "TNF",
                    "stringId_A": "9606.ENSP1",
                    "stringId_B": "9606.ENSP2",
                    "score": 0.62 * 1000,
                },
                {
                    "preferredName_A": "AKT1",
                    "preferredName_B": "EGFR",
                    "stringId_A": "9606.ENSP1",
                    "stringId_B": "9606.ENSP3",
                    "score": 900,
                },
            ],
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        edges = await StringClient(http).network(
            ["AKT1", "TNF", "EGFR"], min_confidence=0.4, network_type="functional"
        )
    assert "/api/json/network" in captured["url"]
    assert "required_score=400" in captured["body"] or "required_score" in captured["body"]
    assert StringEdge("AKT1", "TNF", 0.62) in edges
    assert any(e.confidence == 0.9 for e in edges)


@pytest.mark.asyncio
async def test_network_404_when_no_identifier_resolves_is_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="no identifiers resolved")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        edges = await StringClient(http).network(
            ["NOTAGENE"], min_confidence=0.4, network_type="functional"
        )
    assert edges == []  # honest empty network, not an outage


@pytest.mark.asyncio
async def test_network_outage_raises_503():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(ServiceUnavailableError):
            await StringClient(http).network(
                ["AKT1"], min_confidence=0.4, network_type="functional"
            )
