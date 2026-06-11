import math

import pytest

from app.pipeline.stages import stage5


def _s3(targets):
    # Stage-3 result shape: targets carry target_id + gene info.
    return {
        "targets": [
            {"target_id": t, "gene_symbol": g, "uniprot_accession": u} for (t, g, u) in targets
        ],
        "count": len(targets),
        "state": "computed",
    }


def _s4(rows):
    # Stage-4 result shape: disease_targets carry target_id + score (+ gene info).
    return {
        "disease_targets": [
            {"target_id": t, "gene_symbol": g, "uniprot_accession": u, "score": s}
            for (t, g, u, s) in rows
        ],
        "count": len(rows),
        "state": "computed",
    }


def test_overlap_intersection_and_jaccard():
    s3 = _s3([("t1", "AKT1", "P31749"), ("t2", "TNF", "P01375"), ("t3", "EGFR", "P00533")])
    s4 = _s4(
        [("t2", "TNF", "P01375", 0.7), ("t3", "EGFR", "P00533", 0.5), ("t9", "TP53", "P04637", 0.9)]
    )
    out = stage5.compute(s3, s4)
    ids = {o["target_id"] for o in out["overlap"]}
    assert ids == {"t2", "t3"}
    assert out["count"] == 2
    assert out["compound_target_count"] == 3
    assert out["disease_target_count"] == 3
    assert out["union_count"] == 4  # t1,t2,t3,t9
    assert math.isclose(out["jaccard"], 2 / 4)
    # disease_association_score is carried from S4
    by_id = {o["target_id"]: o for o in out["overlap"]}
    assert by_id["t2"]["disease_association_score"] == 0.7
    assert by_id["t2"]["gene_symbol"] == "TNF"


def test_hypergeometric_significant():
    s3 = _s3([(f"t{i}", f"G{i}", f"P{i}") for i in range(800)])
    s4 = _s4(
        [(f"t{i}", f"G{i}", f"P{i}", 0.5) for i in range(120)]
        + [(f"x{i}", f"H{i}", f"Q{i}", 0.5) for i in range(1380)]
    )
    out = stage5.compute(s3, s4)
    h = out["hypergeometric"]
    assert h["background_n"] == 20000 and h["alpha"] == 0.05
    assert h["k"] == 120
    assert h["p_value"] < 0.05 and h["significant"] is True
    assert out["flags"] == []


def test_non_significant_overlap_flagged():
    # k=1 overlap when E[X] = n*K/N = 100*1000/20000 = 5 -> P(X>=1) >> 0.05 -> not significant
    # s3: 100 compound targets (t0..t99); s4: 1000 disease targets (t0 shared + d1..d999 unique)
    s3 = _s3([(f"t{i}", f"G{i}", f"P{i}") for i in range(100)])
    s4 = _s4([("t0", "G0", "P0", 0.5)] + [(f"d{i}", f"H{i}", f"Q{i}", 0.5) for i in range(999)])
    out = stage5.compute(s3, s4)
    assert out["hypergeometric"]["significant"] is False
    assert "non_significant_overlap" in out["flags"]


def test_zero_overlap_is_count_zero():
    s3 = _s3([("t1", "A", "P1")])
    s4 = _s4([("t2", "B", "P2", 0.5)])
    out = stage5.compute(s3, s4)
    assert out["count"] == 0 and out["overlap"] == []


def test_unmapped_gene_symbol_kept_and_counted():
    s3 = _s3([("t1", None, "P1"), ("t2", "B", "P2")])
    s4 = _s4([("t1", None, "P1", 0.4), ("t2", "B", "P2", 0.6)])
    out = stage5.compute(s3, s4)
    assert out["count"] == 2
    assert out["unmapped_count"] == 1
    assert "unmapped_targets" in out["flags"]


@pytest.mark.asyncio
async def test_run_reads_prior_stage_results():
    run = type("R", (), {})()
    run.stage_results = {
        "3": {
            "targets": [{"target_id": "t1", "gene_symbol": "AKT1", "uniprot_accession": "P31749"}],
            "count": 1,
            "state": "computed",
        },
        "4": {
            "disease_targets": [
                {
                    "target_id": "t1",
                    "gene_symbol": "AKT1",
                    "uniprot_accession": "P31749",
                    "score": 0.8,
                }
            ],
            "count": 1,
            "state": "computed",
        },
    }
    out = await stage5.run(None, run)
    assert out["count"] == 1
    assert out["overlap"][0]["disease_association_score"] == 0.8
