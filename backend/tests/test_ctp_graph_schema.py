"""Unit coverage for the C-T-P graph DTOs (schema mirrors the build_ctp_graph dict shape)."""

from __future__ import annotations

from app.pipeline import results_handoff as rh
from app.schemas.graph import CtpGraph, CtpGraphEdge, CtpGraphNode


def _stage_results() -> dict:
    cid = "11111111-1111-1111-1111-111111111111"
    tid = "22222222-2222-2222-2222-222222222222"
    return {
        "3": {
            "compound_targets": [
                {
                    "compound_id": cid,
                    "target_id": tid,
                    "prediction_method": "chembl_bioactivity",
                }
            ]
        },
        "5": {
            "overlap": [{"target_id": tid, "gene_symbol": "PPARG", "uniprot_accession": "P37231"}]
        },
        "7": {"hubs": [{"target_id": tid, "gene_symbol": "PPARG"}]},
        "8": {
            "terms": [
                {
                    "term_id": "KEGG:04151",
                    "name": "PI3K-Akt",
                    "source": "KEGG",
                    "p_value": 1.2e-4,
                    "intersection": ["PPARG"],
                }
            ]
        },
    }


def test_model_validate_accepts_build_ctp_graph_output() -> None:
    cid = "11111111-1111-1111-1111-111111111111"
    sr = _stage_results()
    compounds_by_id = {
        cid: {"name": "CURCUMIN", "inchi_key": "VFLDPWHFBUODDF-FCXRPNKRSA-N", "smiles": "CC=O"}
    }
    targets_by_id = {
        "22222222-2222-2222-2222-222222222222": {
            "gene_symbol": "PPARG",
            "uniprot_accession": "P37231",
        }
    }

    graph = rh.build_ctp_graph(sr, compounds_by_id, targets_by_id)
    model = CtpGraph.model_validate(graph)

    types = {n.type for n in model.nodes}
    assert {"compound", "target", "pathway"} <= types
    assert all(isinstance(n.id, str) for n in model.nodes)
    interactions = {e.interaction for e in model.edges}
    assert {"compound-target", "target-pathway"} <= interactions


def test_empty_graph_validates() -> None:
    model = CtpGraph.model_validate({"nodes": [], "edges": []})
    assert model.nodes == []
    assert model.edges == []


def test_node_and_edge_fields_are_all_strings() -> None:
    node = CtpGraphNode(
        id="i",
        label="l",
        type="target",
        inchikey="",
        smiles="",
        uniprot_accession="P37231",
        is_hub="true",
        source="",
    )
    edge = CtpGraphEdge(
        source="a", target="b", interaction="compound-target", prediction_method="x", p_value=""
    )
    assert node.uniprot_accession == "P37231"
    assert edge.interaction == "compound-target"
