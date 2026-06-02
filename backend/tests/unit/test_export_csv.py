from app.routers.analyses import _stage2_csv, _stage6_csv


def test_stage6_csv_reads_raw_edges():
    stage_data = {
        "edges": [{"data": {"source": "A", "target": "B", "weight": 900}}],  # nested, must be ignored
        "raw_edges": [
            {"source": "TP53", "target": "EGFR", "combined_score": 950},
            {"source": "AKT1", "target": "MTOR", "combined_score": 700},
        ],
    }
    fieldnames, rows = _stage6_csv(stage_data)
    assert fieldnames == ["source", "target", "combined_score"]
    assert rows[0] == {"source": "TP53", "target": "EGFR", "combined_score": 950}
    assert len(rows) == 2


def test_stage2_csv_includes_failed_and_bypassed():
    stage_data = {
        "compounds": [
            {"compound_id": "c1", "canonical_name": "Pass Mol", "status": "passed",
             "molecular_weight": 300.0, "logp": 2.0, "tpsa": 60.0, "hbond_donors": 1,
             "hbond_acceptors": 3, "np_likeness_score": 0.3, "rotatable_bonds": 4,
             "is_pains_positive": False},
            {"compound_id": "c2", "canonical_name": "Fail Mol", "status": "failed",
             "molecular_weight": 800.0, "logp": 9.0, "tpsa": 200.0, "hbond_donors": 8,
             "hbond_acceptors": 12, "np_likeness_score": 0.1, "rotatable_bonds": 15,
             "is_pains_positive": True},
            {"compound_id": "c3", "canonical_name": "Bypass Mol", "status": "bypassed",
             "molecular_weight": 900.0, "logp": 8.0, "tpsa": 40.0, "hbond_donors": 1,
             "hbond_acceptors": 2, "np_likeness_score": 0.1, "rotatable_bonds": 3,
             "is_pains_positive": False},
        ]
    }
    fieldnames, rows = _stage2_csv(stage_data)
    assert "status" in fieldnames
    assert len(rows) == 3
    statuses = {r["status"] for r in rows}
    assert statuses == {"passed", "failed", "bypassed"}
    assert rows[1]["compound_id"] == "c2"  # failed compound present
