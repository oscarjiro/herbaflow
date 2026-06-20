"""Graph DTOs for the compound-target-pathway (C-T-P) graph endpoint.

These mirror the ``app.pipeline.results_handoff.build_ctp_graph`` dict shape exactly (every
field is a string, matching the de-UUID'd node/edge data that the CSV builders and the chart
already consume). The graph logic itself stays in ``results_handoff``; these are the typed wire
shape so the frontend can render the graph without re-deriving it."""

from __future__ import annotations

from pydantic import BaseModel


class CtpGraphNode(BaseModel):
    id: str
    label: str
    type: str  # "compound" | "target" | "pathway"
    inchikey: str
    smiles: str
    uniprot_accession: str
    is_hub: str  # "true" | "false" | "" (blank for non-target nodes)
    source: str


class CtpGraphEdge(BaseModel):
    source: str
    target: str
    interaction: str  # "compound-target" | "target-pathway"
    prediction_method: str
    p_value: str


class CtpGraph(BaseModel):
    nodes: list[CtpGraphNode]
    edges: list[CtpGraphEdge]
