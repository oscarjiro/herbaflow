"""Stage 6 — PPI network (STRING).

Build the protein–protein interaction network of the Stage-5 overlap's mappable gene symbols
via STRING (confidence-thresholded). The substrate for Stage-7 hubs and Stage-8 enrichment.
Community/module detection is DEFERRED (Methodology §6 scope note) — this stage delivers the
PPI-source row only.

The stage builds on ALL distinct mappable gene symbols. There is no protein-count cap: STRING
imposes no maximum identifier count when the species is set, and this stage always sends 9606.

Result fragment (``stage_results["6"]``):
  - computed: {state, nodes, edges, node_count, edge_count, min_confidence, network_type,
               unmapped, count, flags}
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.string_db import StringClient, StringEdge
from app.pipeline.genes import distinct_gene_symbol_rows

logger = logging.getLogger("herbaflow.pipeline")


def build_result(
    rows: list[dict[str, Any]],
    edges: list[StringEdge],
    *,
    min_confidence: float,
    network_type: str,
) -> dict[str, Any]:
    """Shape STRING edges + the input overlap rows into the stored Stage-6 result.

    Nodes carry the overlap identity (gene_symbol + target_id + uniprot_accession) so Stage 7
    can rank hubs and link each to UniProt. Isolated nodes are reported (honest); genes STRING
    dropped from edges are simply edge-absent. ``unmapped`` records input genes STRING returned
    in NO edge AND no node id (none, since multi-protein queries echo only edges — kept for
    forward-compat).
    """
    seen: set[str] = set()
    nodes: list[dict[str, Any]] = []
    for r in rows:
        g = r["gene_symbol"]
        if g in seen:
            continue
        seen.add(g)
        nodes.append(
            {
                "gene_symbol": g,
                "target_id": r.get("target_id"),
                "uniprot_accession": r.get("uniprot_accession"),
                "string_id": None,
            }
        )
    node_set = set(seen)
    edge_rows = [
        {"source": e.source, "target": e.target, "confidence": e.confidence}
        for e in edges
        if e.source in node_set and e.target in node_set
    ]
    flags: list[str] = []
    if not edge_rows:
        flags.append("sparse_or_empty_network")
    return {
        "state": "computed",
        "nodes": nodes,
        "edges": edge_rows,
        "node_count": len(nodes),
        "edge_count": len(edge_rows),
        "min_confidence": min_confidence,
        "network_type": network_type,
        "unmapped": [],
        "count": len(nodes),
        "flags": flags,
    }


async def run(
    session: AsyncSession | None, run: Any, *, client: StringClient | None = None
) -> dict[str, Any]:
    """Build the STRING network over the Stage-5 overlap and shape the result.

    Mirrors ``stage3.run``: constructs its own ``httpx.AsyncClient`` for the STRING call unless a
    ``client`` is injected (tests). ``session`` is accepted for runner-signature symmetry.
    """
    stage5 = run.stage_results["5"]
    params = run.parameters["ppi"]
    min_confidence = float(params["min_confidence"])
    network_type = str(params["network_type"])

    rows = distinct_gene_symbol_rows(stage5.get("overlap", []))
    symbols = [r["gene_symbol"] for r in rows]

    async def _build(string_client: StringClient) -> dict[str, Any]:
        # ONE client for both calls so they share the throttle (and the httpx session in the
        # non-injected path). The image is supplementary and never fails the stage.
        edges = await string_client.network(
            symbols, min_confidence=min_confidence, network_type=network_type
        )
        image_bytes = await string_client.fetch_network_image(
            symbols, min_confidence=min_confidence, network_type=network_type
        )
        out = build_result(
            rows,
            edges,
            min_confidence=min_confidence,
            network_type=network_type,
        )
        if image_bytes is not None:
            out["network_image"] = base64.b64encode(image_bytes).decode("ascii")
        return out

    if client is not None:
        result = await _build(client)
    else:
        async with httpx.AsyncClient() as http:
            result = await _build(StringClient(http))
    logger.info(
        "stage 6: %d node(s), %d edge(s) at confidence %.2f (%s)",
        result["node_count"],
        result["edge_count"],
        min_confidence,
        network_type,
    )
    return result
