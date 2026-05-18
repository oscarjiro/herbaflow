from analysis.stages.stage5_overlap import compute_overlap


def test_basic_overlap():
    compound_genes = {"TP53", "AKT1", "TNF", "EGFR"}
    disease_genes = {"AKT1", "TNF", "BRCA1"}
    result = compute_overlap(compound_genes, disease_genes)
    assert set(result["overlap"]) == {"AKT1", "TNF"}
    assert result["overlap_count"] == 2
    assert result["compound_only_count"] == 2
    assert result["disease_only_count"] == 1


def test_no_overlap():
    result = compute_overlap({"TP53"}, {"BRCA1"})
    assert result["overlap_count"] == 0
    assert result["jaccard"] == 0.0


def test_jaccard():
    # union={A,B,C}=3, overlap=1 → jaccard=1/3
    result = compute_overlap({"A", "B"}, {"B", "C"})
    assert abs(result["jaccard"] - (1/3)) < 0.001


def test_p_value_significant():
    result = compute_overlap(
        {"TP53", "AKT1", "TNF", "EGFR", "VEGFA"},
        {"TP53", "AKT1", "TNF", "EGFR", "BRCA1"},
        population_size=20000,
    )
    assert result["p_value"] < 0.05


def test_empty_inputs():
    result = compute_overlap(set(), {"BRCA1"})
    assert result["overlap_count"] == 0
