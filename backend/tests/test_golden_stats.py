from scripts.golden import stats


def test_jaccard():
    assert stats.jaccard({"A", "B", "C"}, {"B", "C", "D"}) == 0.5  # 2 / 4
    assert stats.jaccard(set(), set()) == 0.0


def test_overlap_coefficient():
    # |intersect| / min(|a|, |b|) = 2 / 2
    assert stats.overlap_coefficient({"A", "B"}, {"A", "B", "C", "D"}) == 1.0
    assert stats.overlap_coefficient(set(), {"A"}) == 0.0


def test_precision_at_k():
    ranked = ["TP53", "EGFR", "FOO", "BAR", "SMAD3"]
    reference = {"TP53", "EGFR", "SMAD3", "JUN"}
    assert stats.precision_at_k(ranked, reference, k=5) == 0.6  # 3 of 5
    assert stats.precision_at_k(ranked, reference, k=2) == 1.0  # TP53, EGFR
    assert stats.precision_at_k([], reference, k=5) == 0.0
