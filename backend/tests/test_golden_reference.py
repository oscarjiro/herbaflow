from scripts.golden import reference


def test_gd1_reference_loads():
    ref = reference.load_gd1()
    assert "EGFR" in ref.gene_set
    assert ref.universe >= 19000
    assert ref.papers_for("EGFR")  # non-empty
    assert "Han 2021" in ref.papers_for("EGFR")
    assert reference.load_gd1().papers_for("NOT_A_GENE") == []
