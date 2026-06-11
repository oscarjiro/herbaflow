"""Stage 6 — PPI network (STRING).

Build the protein–protein interaction network of the Stage-5 overlap's mappable gene symbols
via STRING (confidence-thresholded). The substrate for Stage-7 hubs and Stage-8 enrichment.
Community/module detection is DEFERRED (Methodology §6 scope note) — this stage delivers the
PPI-source row only.

Cap (PPI-2): n = |distinct mappable gene symbols|.
  - n <= max_proteins -> build on the full set.
  - n > max_proteins and allow_top_n_cap=false -> BLOCKED ({"blocked": true, ...}); the engine
    drives the run status via the AD-6 mechanism (guided park / auto fail). Recover by Redoing
    S6 with allow_top_n_cap=true.
  - allow_top_n_cap=true -> rank overlap by disease_association_score desc, take top max_proteins.

Result fragment (``stage_results["6"]``):
  - computed: {state, nodes, edges, node_count, edge_count, min_confidence, network_type,
               unmapped, capped, count, flags}
  - blocked:  {blocked: true, reason, overlap_count, max_proteins}
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.string_db import StringClient, StringEdge

logger = logging.getLogger("herbaflow.pipeline")


def _mappable(overlap: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Overlap rows with a distinct non-null gene_symbol (first occurrence wins)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in overlap:
        g = row.get("gene_symbol")
        if g and g not in seen:
            seen.add(g)
            out.append(row)
    return out


def select_inputs(
    stage5: dict[str, Any], *, max_proteins: int, allow_top_n_cap: bool
) -> tuple[list[str], dict[str, Any]]:
    """Distinct mappable gene symbols + the cap metadata (assumes n <= cap OR opt-in on)."""
    rows = _mappable(stage5.get("overlap", []))
    capped = {
        "applied": False,
        "max_proteins": max_proteins,
        "ranked_by": "disease_association_score",
    }
    if len(rows) > max_proteins and allow_top_n_cap:
        rows = sorted(rows, key=lambda r: r.get("disease_association_score") or 0.0, reverse=True)[
            :max_proteins
        ]
        capped["applied"] = True
    return [r["gene_symbol"] for r in rows], capped


def compute_blocked_or_inputs(
    stage5: dict[str, Any], *, max_proteins: int, allow_top_n_cap: bool
) -> dict[str, Any]:
    """Either the BLOCKED marker (overflow, opt-in off) or the selected-inputs envelope."""
    n = len(_mappable(stage5.get("overlap", [])))
    if n > max_proteins and not allow_top_n_cap:
        return {
            "blocked": True,
            "reason": "overlap_too_large",
            "overlap_count": n,
            "max_proteins": max_proteins,
        }
    symbols, capped = select_inputs(
        stage5, max_proteins=max_proteins, allow_top_n_cap=allow_top_n_cap
    )
    return {"blocked": False, "symbols": symbols, "capped": capped}


def build_result(
    symbols: list[str],
    edges: list[StringEdge],
    *,
    min_confidence: float,
    network_type: str,
    capped: dict[str, Any],
) -> dict[str, Any]:
    """Shape STRING edges + the input gene set into the stored Stage-6 result.

    Nodes = the mappable input genes (isolated nodes are reported, honest); genes STRING could
    not place still appear as nodes here (the input set), while genes STRING dropped from edges
    are simply edge-absent. ``unmapped`` records input genes STRING returned in NO edge AND no
    node id (none, since multi-protein queries echo only edges — kept for forward-compat).
    """
    node_syms = list(dict.fromkeys(symbols))
    nodes = [{"gene_symbol": g, "string_id": None} for g in node_syms]
    node_set = set(node_syms)
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
    """Cap-check the Stage-5 overlap, call STRING, and shape the network.

    Mirrors ``stage3.run``: constructs its own ``httpx.AsyncClient`` for the STRING call unless a
    ``client`` is injected (tests). ``session`` is accepted for runner-signature symmetry.
    """
    stage5 = run.stage_results["5"]
    params = run.parameters["ppi"]
    min_confidence = float(params["min_confidence"])
    network_type = str(params["network_type"])
    max_proteins = int(params["max_proteins"])
    allow_top_n_cap = bool(params["allow_top_n_cap"])

    envelope = compute_blocked_or_inputs(
        stage5, max_proteins=max_proteins, allow_top_n_cap=allow_top_n_cap
    )
    if envelope["blocked"]:
        logger.info(
            "stage 6: overlap %d > cap %d, opt-in off — blocked",
            envelope["overlap_count"],
            max_proteins,
        )
        return envelope

    symbols = envelope["symbols"]
    if client is not None:
        edges = await client.network(
            symbols, min_confidence=min_confidence, network_type=network_type
        )
    else:
        async with httpx.AsyncClient() as http:
            edges = await StringClient(http).network(
                symbols, min_confidence=min_confidence, network_type=network_type
            )
    result = build_result(
        symbols,
        edges,
        min_confidence=min_confidence,
        network_type=network_type,
        capped=envelope["capped"],
    )
    logger.info(
        "stage 6: %d node(s), %d edge(s) at confidence %.2f (%s)",
        result["node_count"],
        result["edge_count"],
        min_confidence,
        network_type,
    )
    return result
