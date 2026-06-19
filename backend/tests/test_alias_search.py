"""Unit tests for the pure alias-search ranking home.

No DB, no Docker — pure Python only.
"""

from __future__ import annotations

from app.services.alias_search import merge_candidates, rank_match

# ---------------------------------------------------------------------------
# rank_match
# ---------------------------------------------------------------------------


class TestRankMatch:
    """rank_match(term, *, canonical, alias) -> int | None"""

    # --- canonical tiers ---

    def test_canonical_exact(self) -> None:
        assert rank_match("curcumin", canonical="Curcumin") == 0

    def test_canonical_exact_case_insensitive(self) -> None:
        assert rank_match("CURCUMIN", canonical="curcumin") == 0

    def test_canonical_prefix(self) -> None:
        assert rank_match("cur", canonical="Curcumin") == 1

    def test_canonical_prefix_exact_boundary(self) -> None:
        # Full match is exact (0), not prefix (1)
        assert rank_match("curcumin", canonical="Curcumin") == 0

    def test_canonical_substring_not_prefix(self) -> None:
        # "rcum" is in "curcumin" but not a prefix
        assert rank_match("rcum", canonical="Curcumin") == 4

    # --- alias tiers ---

    def test_alias_exact(self) -> None:
        assert rank_match("turmeric", alias="Turmeric") == 2

    def test_alias_prefix(self) -> None:
        assert rank_match("turm", alias="Turmeric") == 3

    def test_alias_substring_not_prefix(self) -> None:
        assert rank_match("meri", alias="Turmeric") == 5

    # --- canonical beats alias ---

    def test_canonical_prefix_beats_alias_exact(self) -> None:
        # rank 1 < rank 2
        c = rank_match("cur", canonical="Curcumin")
        a = rank_match("cur", alias="Curcumin")
        assert c is not None and a is not None
        assert c < a

    def test_canonical_substring_vs_alias_substring(self) -> None:
        # "rcum" is a substring of "curcumin" for BOTH canonical and alias;
        # canonical substring = 4, alias substring = 5 → canonical is better (lower rank).
        c = rank_match("rcum", canonical="Curcumin")
        a = rank_match("rcum", alias="Curcumin")
        assert c == 4
        assert a == 5
        assert c < a  # canonical always beats alias at the same match quality

    def test_alias_exact_beats_canonical_substring(self) -> None:
        # alias exact (2) beats canonical substring (4) — lower rank wins
        c = rank_match("meric", canonical="Turmeric")  # "meric" in "turmeric" → substring → 4
        a = rank_match("meric", alias="meric")  # exact → 2
        assert c == 4
        assert a == 2

    # --- none / empty ---

    def test_canonical_none_returns_none(self) -> None:
        assert rank_match("x", canonical=None) is None

    def test_canonical_empty_returns_none(self) -> None:
        assert rank_match("x", canonical="") is None

    def test_alias_none_returns_none(self) -> None:
        assert rank_match("x", alias=None) is None

    def test_alias_empty_returns_none(self) -> None:
        assert rank_match("x", alias="") is None

    def test_no_hit_canonical(self) -> None:
        assert rank_match("xyz", canonical="Curcumin") is None

    def test_no_hit_alias(self) -> None:
        assert rank_match("xyz", alias="Turmeric") is None

    def test_term_whitespace_stripped_defensively(self) -> None:
        # term already lowercased+stripped by caller, but candidate is stripped defensively
        assert rank_match("curcumin", canonical="  Curcumin  ") == 0

    def test_prefix_not_counted_as_exact(self) -> None:
        # "cur" vs "cur" is exact
        assert rank_match("cur", canonical="cur") == 0
        # "cur " vs "cur" — after strip they are equal
        assert rank_match("cur", canonical="cur ") == 0


# ---------------------------------------------------------------------------
# merge_candidates
# ---------------------------------------------------------------------------


class TestMergeCandidates:
    """merge_candidates(candidates) -> list[tuple[key, rank, matched_alias|None]]"""

    def test_empty_input(self) -> None:
        assert merge_candidates([]) == []

    def test_single_canonical_hit(self) -> None:
        result = merge_candidates([("p1", 0, None)])
        assert result == [("p1", 0, None)]

    def test_single_alias_hit(self) -> None:
        result = merge_candidates([("p1", 2, "turmeric")])
        assert len(result) == 1
        key, rank, alias = result[0]
        assert key == "p1"
        assert rank == 2
        assert alias == "turmeric"

    def test_dedup_canonical_wins_over_alias(self) -> None:
        # Same entity via canonical (rank 1) and alias (rank 2) → keep rank 1, alias=None
        candidates = [
            ("p1", 1, None),  # canonical prefix
            ("p1", 2, "foo"),  # alias exact
        ]
        result = merge_candidates(candidates)
        assert len(result) == 1
        key, rank, alias = result[0]
        assert key == "p1"
        assert rank == 1
        assert alias is None  # canonical win → no matched_alias

    def test_dedup_alias_wins_when_lower_rank(self) -> None:
        # alias exact (2) vs canonical substring (4) — alias wins
        candidates = [
            ("p1", 4, None),  # canonical substring
            ("p1", 2, "foo"),  # alias exact — lower rank, wins
        ]
        result = merge_candidates(candidates)
        assert len(result) == 1
        key, rank, alias = result[0]
        assert key == "p1"
        assert rank == 2
        assert alias == "foo"  # alias win → matched_alias set

    def test_multiple_aliases_best_wins(self) -> None:
        # Two alias rows for the same entity — lowest rank alias wins
        candidates = [
            ("p1", 3, "turm"),  # alias prefix
            ("p1", 5, "meric"),  # alias substring (worse)
        ]
        result = merge_candidates(candidates)
        assert len(result) == 1
        assert result[0][1] == 3
        assert result[0][2] == "turm"

    def test_sort_by_rank_ascending(self) -> None:
        candidates = [
            ("p2", 2, "foo"),
            ("p1", 0, None),
            ("p3", 1, None),
        ]
        result = merge_candidates(candidates)
        ranks = [r[1] for r in result]
        assert ranks == sorted(ranks)

    def test_multiple_entities_distinct(self) -> None:
        candidates = [
            ("p1", 0, None),
            ("p2", 2, "alias-a"),
        ]
        result = merge_candidates(candidates)
        assert len(result) == 2
        keys = {r[0] for r in result}
        assert keys == {"p1", "p2"}

    def test_canonical_hit_clears_matched_alias(self) -> None:
        # If the winning rank is from a canonical row, matched_alias must be None
        # even if a worse alias hit came first in the list
        candidates = [
            ("p1", 2, "alias"),  # alias exact arrives first
            ("p1", 0, None),  # canonical exact — wins
        ]
        result = merge_candidates(candidates)
        assert result[0][1] == 0
        assert result[0][2] is None

    def test_tie_on_rank_stable(self) -> None:
        # Two entities with same rank — both should appear; order stable (rank then key)
        candidates = [
            ("p2", 1, None),
            ("p1", 1, None),
        ]
        result = merge_candidates(candidates)
        assert len(result) == 2
        assert all(r[1] == 1 for r in result)
