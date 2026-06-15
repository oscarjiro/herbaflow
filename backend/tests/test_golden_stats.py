import math

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


def test_fisher_overrepresentation_significant():
    # 9 of 10 hubs are reference genes; reference set is 50 of a 20000 universe.
    res = stats.fisher_overrepresentation(hits=9, drawn=10, reference_size=50, universe=20000)
    assert 0.0 <= res.p_value < 0.05
    assert res.odds_ratio > 1.0


def test_fisher_overrepresentation_not_significant():
    res = stats.fisher_overrepresentation(hits=0, drawn=10, reference_size=50, universe=20000)
    assert res.p_value > 0.05


def test_rank_correlation():
    # identical ordering -> tau = rho = 1.0
    a = ["TP53", "EGFR", "SMAD3", "JUN"]
    b = ["TP53", "EGFR", "SMAD3", "JUN"]
    rc = stats.rank_correlation(a, b)
    assert math.isclose(rc.kendall_tau, 1.0)
    assert math.isclose(rc.spearman_rho, 1.0)
    # only shared genes are correlated; disjoint -> None
    assert stats.rank_correlation(["A"], ["B"]).kendall_tau is None


def test_overlap_at_k():
    a = ["TP53", "EGFR", "JUN", "FOO"]
    b = ["TP53", "EGFR", "SMAD3", "BAR"]
    assert stats.overlap_at_k(a, b, k=3) == 2  # TP53, EGFR
