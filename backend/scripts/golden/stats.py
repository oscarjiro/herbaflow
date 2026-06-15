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
