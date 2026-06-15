# backend/scripts/golden/stats.py
"""Pure, cited agreement statistics for golden-dataset validation.

References:
- Jaccard, P. (1912). New Phytologist 11(2):37-50.
- Manning, Raghavan, Schutze (2008). Introduction to Information Retrieval (precision@k).
- Fisher, R.A. (1935). The Design of Experiments (exact test).
- Spearman (1904); Kendall (1938).
No I/O; every function is deterministic and side-effect free.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from scipy.stats import fisher_exact, kendalltau, spearmanr


def jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def overlap_coefficient(a: set[str], b: set[str]) -> float:
    smaller = min(len(a), len(b))
    if smaller == 0:
        return 0.0
    return len(a & b) / smaller


def precision_at_k(ranked: Sequence[str], reference: Iterable[str], k: int) -> float:
    ref = set(reference)
    top = list(ranked)[:k]
    if not top:
        return 0.0
    return sum(1 for g in top if g in ref) / len(top)


@dataclass(frozen=True)
class OverrepResult:
    p_value: float
    odds_ratio: float
    hits: int
    drawn: int
    reference_size: int
    universe: int


def fisher_overrepresentation(
    *, hits: int, drawn: int, reference_size: int, universe: int
) -> OverrepResult:
    """One-sided Fisher exact test that `drawn` items (the hub set) are enriched for the
    `reference_size` reference genes out of `universe` total genes. 2x2 table:
        [[hits, drawn - hits], [reference_size - hits, universe - drawn - reference_size + hits]].
    """
    in_ref_in_draw = hits
    in_draw_not_ref = drawn - hits
    in_ref_not_draw = reference_size - hits
    neither = universe - drawn - reference_size + hits
    table = [[in_ref_in_draw, in_draw_not_ref], [in_ref_not_draw, neither]]
    odds_ratio, p_value = fisher_exact(table, alternative="greater")
    return OverrepResult(p_value, float(odds_ratio), hits, drawn, reference_size, universe)


@dataclass(frozen=True)
class RankCorrelation:
    kendall_tau: float | None
    spearman_rho: float | None
    shared: int


def rank_correlation(ranking_a: Sequence[str], ranking_b: Sequence[str]) -> RankCorrelation:
    """Rank correlation over the genes present in BOTH rankings, by their 1-based positions."""
    pos_a = {g: i for i, g in enumerate(ranking_a)}
    pos_b = {g: i for i, g in enumerate(ranking_b)}
    shared = [g for g in ranking_a if g in pos_b]
    if len(shared) < 2:
        return RankCorrelation(None, None, len(shared))
    xs = [pos_a[g] for g in shared]
    ys = [pos_b[g] for g in shared]
    tau, _ = kendalltau(xs, ys)
    rho, _ = spearmanr(xs, ys)
    return RankCorrelation(float(tau), float(rho), len(shared))


def overlap_at_k(ranking_a: Sequence[str], ranking_b: Sequence[str], k: int) -> int:
    return len(set(ranking_a[:k]) & set(ranking_b[:k]))
