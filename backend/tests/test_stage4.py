from app.pipeline.stages import stage4

ROWS = [
    {
        "target_id": "11111111-1111-5111-8111-111111111111",
        "gene_symbol": "GENEA",
        "uniprot_accession": "P11111",
        "source_url": "https://u/P11111/entry",
        "score": 0.9,
        "association_type": "overall",
    },
    {
        "target_id": "22222222-2222-5222-8222-222222222222",
        "gene_symbol": None,
        "uniprot_accession": "P22222",
        "source_url": None,
        "score": 0.4,
        "association_type": "overall",
    },
]


def test_compute_shapes_targets_and_carries_score():
    result = stage4.compute(ROWS, 0.3)
    assert result["state"] == "computed"
    assert result["count"] == 2
    assert result["min_score_applied"] == 0.3
    # Entity list the edit layer will tag (target_id + a display name fallback).
    assert {t["target_id"] for t in result["targets"]} == {
        "11111111-1111-5111-8111-111111111111",
        "22222222-2222-5222-8222-222222222222",
    }
    assert result["targets"][0]["canonical_name"] == "GENEA"
    # Missing gene symbol falls back to the accession for display.
    assert result["targets"][1]["canonical_name"] == "P22222"
    # disease_targets carry the score + association_type + link for the view (DT4-9).
    dt = {d["target_id"]: d for d in result["disease_targets"]}
    assert dt["11111111-1111-5111-8111-111111111111"]["score"] == 0.9
    assert dt["11111111-1111-5111-8111-111111111111"]["association_type"] == "overall"


def test_compute_empty_side_is_valid_not_a_hard_stop():
    result = stage4.compute([], 0.9)
    assert result["count"] == 0
    assert result["state"] == "computed"
    assert result["disease_targets"] == []
    assert result["targets"] == []
