import httpx
import pytest

from app.integrations.gprofiler import GprofilerClient, GprofilerError


def _result_row(**kw):
    base = {
        "name": "PI3K-Akt signaling pathway",
        "native": "KEGG:04151",
        "source": "KEGG",
        "p_value": 3.1e-6,
        "term_size": 354,
        "query_size": 3,
        "intersection_size": 2,
        "significant": True,
        "intersections": [["IEA"], ["IEA"], []],
    }
    base.update(kw)
    return base


@pytest.mark.asyncio
async def test_profile_builds_custom_background_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"result": [_result_row()]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        terms = await GprofilerClient(http).profile(
            query=["AKT1", "TNF", "IL6"],
            background=["AKT1", "TNF", "IL6", "EGFR", "TP53"],
            sources=["GO:BP", "KEGG"],
            correction="fdr",
            user_threshold=0.05,
        )
    assert "/api/gost/profile/" in captured["url"]
    b = captured["body"]
    assert b["organism"] == "hsapiens"
    assert b["query"] == ["AKT1", "TNF", "IL6"]
    assert b["domain_scope"] == "custom"
    assert b["background"] == ["AKT1", "TNF", "IL6", "EGFR", "TP53"]
    assert b["significance_threshold_method"] == "fdr"
    assert b["user_threshold"] == 0.05
    assert b["no_evidences"] is False
    # the first term's intersection genes are recovered by zipping query <-> intersections
    assert terms[0].native == "KEGG:04151"
    assert terms[0].intersection == ["AKT1", "TNF"]  # third query gene had [] evidence
    assert terms[0].intersection_size == 2
    assert terms[0].term_size == 354


@pytest.mark.asyncio
async def test_profile_outage_raises_gprofiler_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(GprofilerError):
            await GprofilerClient(http).profile(
                query=["AKT1"],
                background=["AKT1", "EGFR"],
                sources=["GO:BP"],
                correction="fdr",
                user_threshold=0.05,
            )


@pytest.mark.asyncio
async def test_profile_empty_query_returns_empty_without_calling():
    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200, json={"result": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        terms = await GprofilerClient(http).profile(
            query=[],
            background=["AKT1"],
            sources=["GO:BP"],
            correction="fdr",
            user_threshold=0.05,
        )
    assert terms == [] and called["n"] == 0
