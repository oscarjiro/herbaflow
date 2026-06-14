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
    # Stage-4 result shape: ONE enriched edit-layer targets list.
    return {
        "targets": [
            {"target_id": t, "gene_symbol": g, "uniprot_accession": u, "opentargets_score": s}
            for (t, g, u, s) in rows
        ],
        "count": len(rows),
        "state": "computed",
    }


def test_overlap_is_pure_intersection_with_side_counts():
    s3 = _s3([("t1", "AKT1", "P31749"), ("t2", "TNF", "P01375"), ("t3", "EGFR", "P00533")])
    s4 = _s4(
        [("t2", "TNF", "P01375", 0.7), ("t3", "EGFR", "P00533", 0.5), ("t9", "TP53", "P04637", 0.9)]
    )
    out = stage5.compute(s3, s4)
    assert {o["target_id"] for o in out["overlap"]} == {"t2", "t3"}
    assert out["count"] == 2
    assert out["compound_target_count"] == 3
    assert out["disease_target_count"] == 3
    by_id = {o["target_id"]: o for o in out["overlap"]}
    assert by_id["t2"]["opentargets_score"] == 0.7
    assert by_id["t2"]["gene_symbol"] == "TNF"


def test_no_statistics_keys():
    out = stage5.compute(_s3([("t1", "A", "P1")]), _s4([("t1", "A", "P1", 0.5)]))
    for k in ("jaccard", "union_count", "hypergeometric", "significant"):
        assert k not in out


def test_zero_overlap_is_count_zero():
    out = stage5.compute(_s3([("t1", "A", "P1")]), _s4([("t2", "B", "P2", 0.5)]))
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
            "targets": [
                {
                    "target_id": "t1",
                    "gene_symbol": "AKT1",
                    "uniprot_accession": "P31749",
                    "opentargets_score": 0.8,
                }
            ],
            "count": 1,
            "state": "computed",
        },
    }
    out = await stage5.run(None, run)
    assert out["count"] == 1
    assert out["overlap"][0]["opentargets_score"] == 0.8


def test_user_removed_targets_excluded_on_both_sides():
    """A target tagged ``user-removed`` on EITHER side is excluded; reported sizes are effective."""
    s3 = {
        "targets": [
            {"target_id": "t1", "gene_symbol": "A", "uniprot_accession": "P1", "tag": "computed"},
            {"target_id": "t2", "gene_symbol": "B", "uniprot_accession": "P2", "tag": "computed"},
            {
                "target_id": "t3",
                "gene_symbol": "C",
                "uniprot_accession": "P3",
                "tag": "user-removed",
            },
        ],
        "count": 2,
        "state": "user_provided",
    }
    s4 = {
        "targets": [
            {
                "target_id": "t1",
                "gene_symbol": "A",
                "uniprot_accession": "P1",
                "opentargets_score": 0.7,
                "tag": "computed",
            },
            {
                "target_id": "t2",
                "gene_symbol": "B",
                "uniprot_accession": "P2",
                "opentargets_score": 0.6,
                "tag": "user-removed",
            },
            {
                "target_id": "t3",
                "gene_symbol": "C",
                "uniprot_accession": "P3",
                "opentargets_score": 0.5,
                "tag": "computed",
            },
        ],
        "count": 2,
        "state": "user_provided",
    }
    out = stage5.compute(s3, s4)
    assert {o["target_id"] for o in out["overlap"]} == {"t1"}
    assert out["count"] == 1
    assert out["compound_target_count"] == 2
    assert out["disease_target_count"] == 2
