"""STRING client — protein–protein interaction network for the overlap targets.

Written to the verified STRING REST contract (string-db.org/help/api, 2026-06-11):
POST /api/json/network; identifiers newline-joined; species=9606 (mandatory >10 proteins);
required_score = round(min_confidence*1000), 0–1000; network_type functional|physical;
caller_identity set; ~1 request/second. Response rows carry preferredName_A/B and a combined
``score`` on 0–1000. STRING returns **404 when none of the submitted identifiers resolve** ->
an honest empty network (NOT an outage). A 5xx/transport failure is load-bearing -> 503.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

from app.errors import ServiceUnavailableError
from app.integrations.base import with_retry

logger = logging.getLogger("herbaflow.integrations.string")

_URL = "https://string-db.org/api/json/network"
_IMAGE_URL = "https://string-db.org/api/highres_image/network"
_SPECIES = 9606
_CALLER = "herbaflow"
_MIN_INTERVAL = 1.0  # ~1 req/s (STRING guidance)
_SEM = asyncio.Semaphore(1)
_last_call = 0.0


def _network_body(symbols: list[str], min_confidence: float, network_type: str) -> dict[str, str]:
    """Form body shared by the JSON network call and the server-rendered image call."""
    return {
        "identifiers": "\r".join(symbols),
        "species": str(_SPECIES),
        "required_score": str(round(min_confidence * 1000)),
        "network_type": network_type,
        "caller_identity": _CALLER,
    }


@dataclass(frozen=True)
class StringEdge:
    source: str
    target: str
    confidence: float  # 0–1


class StringClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def _throttled_post(self, url: str, body: dict[str, str]) -> httpx.Response:
        """POST honoring STRING's shared ~1 req/s budget (the JSON and image calls share it)."""
        global _last_call
        async with _SEM:
            wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            resp = await self._client.post(url, data=body, timeout=60.0)
            _last_call = time.monotonic()
        return resp

    async def network(
        self, gene_symbols: list[str], *, min_confidence: float, network_type: str
    ) -> list[StringEdge]:
        """Edges among ``gene_symbols`` at the confidence floor. Empty input -> []."""
        symbols = [g for g in gene_symbols if g]
        if not symbols:
            return []
        required_score = round(min_confidence * 1000)
        body = _network_body(symbols, min_confidence, network_type)

        async def _call() -> httpx.Response:
            resp = await self._throttled_post(_URL, body)
            if resp.status_code == 404:
                return resp  # all-unresolved -> handled below, not retried
            resp.raise_for_status()
            return resp

        try:
            resp = await with_retry(_call)
        except httpx.HTTPError as exc:
            logger.warning("STRING outage: %s", exc)
            raise ServiceUnavailableError(detail="STRING is unavailable.") from exc

        if resp.status_code == 404:
            logger.info(
                "STRING: no identifiers resolved (%d submitted) — empty network", len(symbols)
            )
            return []

        edges: list[StringEdge] = []
        for row in resp.json():
            a = row.get("preferredName_A")
            b = row.get("preferredName_B")
            score = row.get("score")
            if not a or not b or score is None:
                continue
            conf = float(score) / 1000.0 if float(score) > 1 else float(score)
            edges.append(StringEdge(a, b, round(conf, 3)))
        logger.info(
            "STRING: %d edge(s) among %d input genes (required_score=%d)",
            len(edges),
            len(symbols),
            required_score,
        )
        return edges

    async def fetch_network_image(
        self, gene_symbols: list[str], *, min_confidence: float, network_type: str
    ) -> bytes | None:
        """STRING's own server-rendered PPI network image (high-res PNG) for the overlap genes.

        SUPPLEMENTARY, degrade-never-fail: returns the PNG bytes on success, or None on an
        empty input or ANY error (non-200, 404, timeout, transport, malformed) so the export's
        PPI figure can fall back to the local matplotlib render and the run never fails on it.
        Contrast network(), which is load-bearing (raises 503 on outage)."""
        symbols = [g for g in gene_symbols if g]
        if not symbols:
            return None
        body = _network_body(symbols, min_confidence, network_type)
        try:
            resp = await self._throttled_post(_IMAGE_URL, body)
        except httpx.HTTPError as exc:  # timeout/transport/protocol — degrade, do not raise
            logger.info("STRING image unavailable, falling back to local render: %s", exc)
            return None
        if resp.status_code != 200:
            logger.info("STRING image returned %d, falling back to local render", resp.status_code)
            return None
        return resp.content
