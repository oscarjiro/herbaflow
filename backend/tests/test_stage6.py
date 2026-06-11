from app.integrations.string_db import StringEdge
from app.pipeline.stages import stage6


def _overlap(n, base_score=0.5):
    return {
        "overlap": [
            {
                "target_id": f"t{i}",
                "gene_symbol": f"G{i}",
                "uniprot_accession": f"P{i}",
                "disease_association_score": base_score + i * 0.001,
            }
            for i in range(n)
        ],
        "count": n,
        "state": "computed",
    }


def test_select_under_cap_uses_all():
    sel, capped = stage6.select_inputs(_overlap(5), max_proteins=2000, allow_top_n_cap=False)
    assert {s for s in sel} == {f"G{i}" for i in range(5)}
    assert capped["applied"] is False


def test_over_cap_without_optin_is_blocked():
    out = stage6.compute_blocked_or_inputs(_overlap(3), max_proteins=2, allow_top_n_cap=False)
    assert out["blocked"] is True
    assert out["reason"] == "overlap_too_large"
    assert out["overlap_count"] == 3 and out["max_proteins"] == 2


def test_over_cap_with_optin_takes_top_n_by_score():
    sel, capped = stage6.select_inputs(_overlap(3), max_proteins=2, allow_top_n_cap=True)
    # highest disease_association_score first: G2 (0.502), G1 (0.501)
    assert set(sel) == {"G2", "G1"}
    assert capped["applied"] is True and capped["ranked_by"] == "disease_association_score"


def test_build_result_parses_edges_and_nodes():
    edges = [StringEdge("G0", "G1", 0.6)]
    out = stage6.build_result(
        ["G0", "G1", "G2"],
        edges,
        min_confidence=0.4,
        network_type="functional",
        capped={"applied": False, "max_proteins": 2000, "ranked_by": "disease_association_score"},
    )
    assert out["state"] == "computed"
    assert out["edge_count"] == 1 and out["node_count"] == 3
    # G2 has no edge but is an isolated node, still listed
    assert {n["gene_symbol"] for n in out["nodes"]} == {"G0", "G1", "G2"}
    assert out["count"] == 3
