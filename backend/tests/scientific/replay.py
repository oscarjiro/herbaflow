"""Shared offline-replay doubles for the golden (GD-*) scientific regressions.

One home for the deterministic test doubles both golden datasets replay, so GD-1 and GD-2 (and their
report drivers) build the SAME recorded clients instead of each defining a near-identical pair:

- ``ReplayString`` replays a recorded STRING network, scoped to the called gene set. The filter is
  a no-op when the full recorded gene set is passed (GD-1, whose network was captured over its
  overlap) and reproduces the 233-gene network from the 247-gene recording when the smaller set is
  passed (GD-2), so one recorded network serves both. The server-rendered image is absent (None);
  the image step can never fail the stage.
- ``ReplayGprofiler`` replays a fixed term list: GD-1's recorded terms, or GD-2's empty enrichment
  (Stage 8 honest-null).
- ``forbid_stage3_clients`` installs raise-if-called guards on every Stage-3 external client so the
  offline manual / D9 edge-reuse path never constructs a live client.
"""

from __future__ import annotations

from typing import Any

from app.integrations.gprofiler import EnrichedTerm
from app.integrations.string_db import StringEdge
from app.pipeline.stages import stage3


class ReplayString:
    """Replay recorded STRING edges, scoped to the called gene set.

    Returns only edges whose source AND target are both in ``gene_symbols``. Passing the full
    recorded gene set makes the filter a no-op; passing a subset reproduces that subset's network.
    """

    def __init__(self, edges: list[dict[str, Any]]) -> None:
        self._edges = edges

    async def network(
        self, gene_symbols: list[str], *, min_confidence: float, network_type: str
    ) -> list[StringEdge]:
        called = set(gene_symbols)
        return [
            StringEdge(e["source"], e["target"], e["confidence"])
            for e in self._edges
            if e["source"] in called and e["target"] in called
        ]

    async def fetch_network_image(
        self, gene_symbols: list[str], *, min_confidence: float, network_type: str
    ) -> bytes | None:
        return None


class ReplayGprofiler:
    """Replay a fixed enrichment term list (recorded terms, or empty for an honest-null Stage 8)."""

    def __init__(self, terms: list[EnrichedTerm]) -> None:
        self._terms = terms

    async def profile(
        self,
        *,
        query: list[str],
        background: list[str],
        sources: list[str],
        correction: str,
        user_threshold: float,
        no_iea: bool = False,
    ) -> list[EnrichedTerm]:
        return list(self._terms)


class _RaiseIfCalled:
    """A Stage-3 external client whose construction is forbidden in the offline golden runs.

    The offline path (manual targets, or D9 edge-reuse) never fetches; building any Stage-3 client
    would mean the offline contract broke, and this guard trips loudly instead of calling out.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("external call in offline golden test")


def forbid_stage3_clients(monkeypatch: Any) -> None:
    """Forbid every Stage-3 external client; trips loudly if the offline path ever fetches."""
    monkeypatch.setattr(stage3, "ChemblClient", _RaiseIfCalled)
    monkeypatch.setattr(stage3, "PubChemBioAssayClient", _RaiseIfCalled)
    monkeypatch.setattr(stage3, "UniProtClient", _RaiseIfCalled)
