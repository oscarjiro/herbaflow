"""Stage 6 — PPI network (STRING).

Build the protein–protein interaction network of the Stage-5 overlap's mappable gene symbols
via STRING (confidence-thresholded). The substrate for Stage-7 hubs and Stage-8 enrichment.
Community/module detection is DEFERRED (Methodology §6 scope note) — this stage delivers the
PPI-source row only.

STR-1 (2026-07-06): STRING imposes no identifier cap; caps disabled, reversible — restore to
re-enable. The self-imposed max_proteins cap and the "overlap too large" blocked-overflow marker
are DISABLED: the stage builds on ALL distinct mappable gene symbols and never emits a blocked
result. The ``max_proteins``/``allow_top_n_cap`` params stay defined in the contract but are inert.
The cap-select + blocked logic is commented (below + in the engine); restore it to re-enable.

Result fragment (``stage_results["6"]``):
  - computed: {state, nodes, edges, node_count, edge_count, min_confidence, network_type,
               unmapped, capped, count, flags}
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


# STR-1 (2026-07-06): STRING imposes no identifier cap; caps disabled, reversible — restore to
# re-enable. The self-imposed max_proteins cap + "overlap too large" blocked marker are off.
# ``run`` now passes ALL distinct mappable overlap gene symbols to STRING (never blocked). The
# helpers below are the cap-select + blocked-marker logic; restore them (and their call in ``run``)
# to re-enable the cap.
#
# def select_inputs(
#     stage5: dict[str, Any], *, max_proteins: int, allow_top_n_cap: bool
# ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
#     """Distinct mappable overlap ROWS + the cap metadata (assumes n <= cap OR opt-in on)."""
#     rows = distinct_gene_symbol_rows(stage5.get("overlap", []))
#     capped = {
#         "applied": False,
#         "max_proteins": max_proteins,
#         "ranked_by": "opentargets_score",
#     }
#     if len(rows) > max_proteins and allow_top_n_cap:
#         rows = sorted(rows, key=lambda r: r.get("opentargets_score") or 0.0, reverse=True)[
#             :max_proteins
#         ]
#         capped["applied"] = True
#     return rows, capped
#
#
# def compute_blocked_or_inputs(
#     stage5: dict[str, Any], *, max_proteins: int, allow_top_n_cap: bool
# ) -> dict[str, Any]:
#     """Either the BLOCKED marker (overflow, opt-in off) or the selected-rows envelope."""
#     n = len(distinct_gene_symbol_rows(stage5.get("overlap", [])))
#     if n > max_proteins and not allow_top_n_cap:
#         return {
#             "blocked": True,
#             "reason": "overlap_too_large",
#             "overlap_count": n,
#             "max_proteins": max_proteins,
#         }
#     rows, capped = select_inputs(
#         stage5, max_proteins=max_proteins, allow_top_n_cap=allow_top_n_cap
#     )
#     return {"blocked": False, "rows": rows, "capped": capped}


def build_result(
    rows: list[dict[str, Any]],
    edges: list[StringEdge],
    *,
    min_confidence: float,
    network_type: str,
    capped: dict[str, Any],
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
        "capped": capped,
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

    # STR-1 (2026-07-06): STRING imposes no identifier cap; caps disabled, reversible — restore to
    # re-enable. Use ALL distinct mappable overlap rows — no cap, never blocked. The commented block
    # below is the cap-check + blocked-overflow path; restore it (+ the helpers above) to re-enable.
    # max_proteins = int(params["max_proteins"])
    # allow_top_n_cap = bool(params["allow_top_n_cap"])
    #
    # envelope = compute_blocked_or_inputs(
    #     stage5, max_proteins=max_proteins, allow_top_n_cap=allow_top_n_cap
    # )
    # if envelope["blocked"]:
    #     logger.info(
    #         "stage 6: overlap %d > cap %d, opt-in off — blocked",
    #         envelope["overlap_count"],
    #         max_proteins,
    #     )
    #     return envelope
    #
    # rows = envelope["rows"]
    rows = distinct_gene_symbol_rows(stage5.get("overlap", []))
    capped = {"applied": False, "max_proteins": None, "ranked_by": "opentargets_score"}
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
            capped=capped,
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
