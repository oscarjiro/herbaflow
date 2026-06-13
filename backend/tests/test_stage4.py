from app.pipeline.stages import stage4

ROWS = [
    {
        "target_id": "11111111-1111-5111-8111-111111111111",
        "gene_symbol": "GENEA",
        "uniprot_accession": "P11111",
        "source_url": "https://u/P11111/entry",
        "opentargets_score": 0.9,
        "association_type": "overall",
    },
    {
        "target_id": "22222222-2222-5222-8222-222222222222",
        "gene_symbol": None,
        "uniprot_accession": "P22222",
        "source_url": None,
        "opentargets_score": 0.4,
        "association_type": "overall",
    },
]


def test_compute_emits_one_enriched_targets_list():
    result = stage4.compute(ROWS, 0.3)
    assert result["state"] == "computed"
    assert result["count"] == 2
    assert result["min_score_applied"] == 0.3
    # ONE enriched list (no separate disease_targets view list — B-DUP-2 / L-11).
    assert "disease_targets" not in result
    assert {t["target_id"] for t in result["targets"]} == {
        "11111111-1111-5111-8111-111111111111",
        "22222222-2222-5222-8222-222222222222",
    }
    by_id = {t["target_id"]: t for t in result["targets"]}
    first = by_id["11111111-1111-5111-8111-111111111111"]
    # Display-name fallback (gene_symbol -> accession -> id).
    assert first["canonical_name"] == "GENEA"
    # The association fields ride on the single targets list now.
    assert first["gene_symbol"] == "GENEA"
    assert first["uniprot_accession"] == "P11111"
    assert first["opentargets_score"] == 0.9
    assert first["association_type"] == "overall"
    assert first["source_url"] == "https://u/P11111/entry"
    # Missing gene symbol falls back to the accession for display.
    assert by_id["22222222-2222-5222-8222-222222222222"]["canonical_name"] == "P22222"


def test_compute_empty_side_is_valid_not_a_hard_stop():
    result = stage4.compute([], 0.9)
    assert result["count"] == 0
    assert result["state"] == "computed"
    assert "disease_targets" not in result
    assert result["targets"] == []
