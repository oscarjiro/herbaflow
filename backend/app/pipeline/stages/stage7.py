"""Stage 7 — Hub genes (networkx centralities + hub-bottleneck composite).

Rank the Stage-6 PPI proteins by network centrality so the key mechanistic players surface.
Four classic centralities (degree, betweenness, closeness, eigenvector) are computed on the
UNDIRECTED PPI graph and reported alongside a weighted hub-bottleneck composite
(``w·norm(degree) + (1−w)·norm(betweenness)``, Yu 2007), min-max normalised. Pure
computation (networkx); NO external API.

Reads ``stage_results["6"]`` (nodes carry gene_symbol + target_id + uniprot_accession; edges
carry source/target gene symbols + confidence). The graph node identity is the gene symbol
(STRING ``preferredName``); identity (target_id, UniProt link) is recovered from the node rows.

Result fragment (``stage_results["7"]``); ``count`` = number of hubs reported:
  - ``hubs``: [{rank, target_id, gene_symbol, degree, betweenness, closeness, eigenvector,
               composite, source_url}]
  - ``ranking_metric`` / ``composite_weight`` / ``normalization`` / ``node_count`` / ``top_n``
  - ``flags`` (``network_too_small`` / ``eigenvector_fallback``)

Edge cases (Methodology §7.6 / spec HB-2/3): tiny/edgeless network -> ``network_too_small`` flag
(reported, not a hard-stop); eigenvector non-convergence -> numpy fallback + flag; ties broken
deterministically by (gene_symbol, target_id); ``top_n`` > node_count -> all.
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("herbaflow.pipeline")

_MIN_INFORMATIVE_NODES = 3  # below this (or edgeless) centrality is near-meaningless (§7.6)


def _min_max(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalise to [0,1]; a flat distribution maps to all-zeros (no spread)."""
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if hi == lo:
        return {k: 0.0 for k in values}
    span = hi - lo
    return {k: (v - lo) / span for k, v in values.items()}


def compute(
    stage6: dict[str, Any], *, top_n: int, use_hub_bottleneck: bool, composite_weight: float
) -> dict[str, Any]:
    """Pure centrality ranking from the stored Stage-6 network."""
    meta = {n["gene_symbol"]: n for n in stage6.get("nodes", [])}
    edges = stage6.get("edges", [])

    graph = nx.Graph()
    graph.add_nodes_from(meta.keys())
    for e in edges:
        s, d = e.get("source"), e.get("target")
        if s in meta and d in meta and s != d:
            graph.add_edge(s, d, weight=e.get("confidence") or 1.0)

    n_nodes = graph.number_of_nodes()
    n_edges = graph.number_of_edges()
    flags: list[str] = []

    if n_nodes == 0:
        return {
            "state": "computed",
            "hubs": [],
            "ranking_metric": "hub_bottleneck_composite" if use_hub_bottleneck else "degree",
            "composite_weight": composite_weight,
            "normalization": "min_max",
            "node_count": 0,
            "top_n": top_n,
            "count": 0,
            "flags": ["network_too_small"],
        }

    degree = nx.degree_centrality(graph)
    betweenness = nx.betweenness_centrality(graph)
    closeness = nx.closeness_centrality(graph)
    if n_edges == 0:
        eigenvector = {g: 0.0 for g in graph}
    else:
        try:
            eigenvector = nx.eigenvector_centrality(graph, max_iter=1000)
        except nx.PowerIterationFailedConvergence:
            eigenvector = nx.eigenvector_centrality_numpy(graph)
            flags.append("eigenvector_fallback")

    deg_norm = _min_max(degree)
    betw_norm = _min_max(betweenness)
    if use_hub_bottleneck:
        composite = {
            g: composite_weight * deg_norm[g] + (1.0 - composite_weight) * betw_norm[g]
            for g in graph
        }
        ranking_metric = "hub_bottleneck_composite"
    else:
        composite = dict(degree)
        ranking_metric = "degree"

    # Deterministic ranking: composite desc, then gene_symbol asc, then target_id asc.
    ordered = sorted(
        graph.nodes(),
        key=lambda g: (-composite[g], g, str(meta[g].get("target_id") or "")),
    )

    if n_nodes < _MIN_INFORMATIVE_NODES or n_edges == 0:
        flags.append("network_too_small")

    keep = ordered if top_n >= n_nodes else ordered[:top_n]
    hubs: list[dict[str, Any]] = []
    for rank, g in enumerate(keep, start=1):
        node = meta[g]
        acc = node.get("uniprot_accession")
        hubs.append(
            {
                "rank": rank,
                "target_id": node.get("target_id"),
                "gene_symbol": g,
                "degree": round(degree[g], 6),
                "betweenness": round(betweenness[g], 6),
                "closeness": round(closeness[g], 6),
                "eigenvector": round(eigenvector[g], 6),
                "composite": round(composite[g], 6),
                "source_url": (f"https://www.uniprot.org/uniprotkb/{acc}/entry" if acc else None),
            }
        )

    return {
        "state": "computed",
        "hubs": hubs,
        "ranking_metric": ranking_metric,
        "composite_weight": composite_weight,
        "normalization": "min_max",
        "node_count": n_nodes,
        "top_n": top_n,
        "count": len(hubs),
        "flags": flags,
    }


async def run(session: AsyncSession | None, run: Any) -> dict[str, Any]:
    """Rank hubs from the run's stored Stage-6 network. Pure read; ``session`` is for symmetry."""
    stage6 = run.stage_results["6"]
    params = run.parameters["hub_genes"]
    result = compute(
        stage6,
        top_n=int(params["top_n"]),
        use_hub_bottleneck=bool(params["use_hub_bottleneck"]),
        composite_weight=float(params["composite_weight"]),
    )
    logger.info(
        "stage 7: %d hub(s) of %d node(s) (metric=%s, w=%.2f)%s",
        result["count"],
        result["node_count"],
        result["ranking_metric"],
        result["composite_weight"],
        f" flags={result['flags']}" if result["flags"] else "",
    )
    return result
