"""Stage 7 — Hub genes (networkx centralities + Maximal Clique Centrality).

Rank the Stage-6 PPI proteins by Maximal Clique Centrality (MCC; Chin et al. 2014, cytoHubba),
the field-standard single-method hub ranker. Four classic centralities (degree, betweenness,
closeness, eigenvector) are computed on the UNDIRECTED PPI graph and REPORTED alongside the MCC
score for transparency; they are no longer aggregated into the ranking. Pure computation
(networkx); NO external API.

MCC(v) = sum over maximal cliques C containing v of (|C| - 1)!  (Chin 2014). Computed on the
undirected, unweighted graph via Bron-Kerbosch maximal-clique enumeration (nx.find_cliques). Only
cliques of size >= 2 are counted, so an isolated node scores 0 (== its degree), matching the
paper's "no edge between the neighbours of v -> MCC(v) == degree(v)" special case.

Reads ``stage_results["6"]`` (nodes carry gene_symbol + target_id + uniprot_accession; edges carry
source/target gene symbols + confidence). The graph node identity is the gene symbol (STRING
``preferredName``); identity (target_id, UniProt link) is recovered from the node rows.

Result fragment (``stage_results["7"]``); ``count`` = number of hubs reported:
  - ``hubs``: [{rank, target_id, gene_symbol, degree, betweenness, closeness, eigenvector, mcc,
               source_url}]
  - ``ranking_metric`` (always "mcc") / ``node_count`` / ``top_n``
  - ``flags`` (``network_too_small`` / ``eigenvector_fallback``)

Edge cases (Methodology §7.6): tiny/edgeless network -> ``network_too_small`` flag (reported, not a
hard-stop); eigenvector non-convergence -> numpy fallback + flag; ties broken deterministically by
(mcc desc, degree desc, gene_symbol, target_id); ``top_n`` > node_count -> all.
"""

from __future__ import annotations

import logging
from math import factorial
from typing import Any

import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("herbaflow.pipeline")

_MIN_INFORMATIVE_NODES = 3  # below this (or edgeless) centrality is near-meaningless (§7.6)


def _mcc(graph: nx.Graph) -> dict[str, int]:
    """Maximal Clique Centrality (Chin 2014): MCC(v) = sum over maximal cliques C containing v of
    (|C|-1)!. Only cliques of size >= 2 are counted, so an isolated node (singleton clique) scores
    0 == its degree, per the paper's "no edge between neighbours -> MCC == degree" special case.
    Undirected, unweighted topology (nx.find_cliques ignores edge weights)."""
    mcc: dict[str, int] = {v: 0 for v in graph}
    for clique in nx.find_cliques(graph):
        if len(clique) < 2:
            continue
        f = factorial(len(clique) - 1)
        for v in clique:
            mcc[v] += f
    return mcc


def compute(stage6: dict[str, Any], *, top_n: int) -> dict[str, Any]:
    """Pure MCC hub ranking from the stored Stage-6 network."""
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
            "ranking_metric": "mcc",
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

    mcc = _mcc(graph)

    # Deterministic ranking: mcc desc, degree desc, gene_symbol asc, target_id asc.
    ordered = sorted(
        graph.nodes(),
        key=lambda g: (-mcc[g], -degree[g], g, str(meta[g].get("target_id") or "")),
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
                "mcc": mcc[g],
                "source_url": (f"https://www.uniprot.org/uniprotkb/{acc}/entry" if acc else None),
            }
        )

    return {
        "state": "computed",
        "hubs": hubs,
        "ranking_metric": "mcc",
        "node_count": n_nodes,
        "top_n": top_n,
        "count": len(hubs),
        "flags": flags,
    }


async def run(session: AsyncSession | None, run: Any) -> dict[str, Any]:
    """Rank hubs from the run's stored Stage-6 network. Pure read; ``session`` is for symmetry."""
    stage6 = run.stage_results["6"]
    params = run.parameters["hub_genes"]
    result = compute(stage6, top_n=int(params["top_n"]))
    logger.info(
        "stage 7: %d hub(s) of %d node(s) (metric=%s)%s",
        result["count"],
        result["node_count"],
        result["ranking_metric"],
        f" flags={result['flags']}" if result["flags"] else "",
    )
    return result
