"""Pure alias-search ranking helpers.

No DB, no I/O — fully unit-testable in isolation.

Rank scale (lower wins):
    0  canonical exact
    1  canonical prefix (startswith)
    2  alias exact
    3  alias prefix
    4  canonical substring (not prefix/exact)
    5  alias substring (not prefix/exact)
    None  no hit
"""

from __future__ import annotations

from collections.abc import Hashable

# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #


def rank_match(
    term: str,
    *,
    canonical: str | None = None,
    alias: str | None = None,
) -> int | None:
    """Rank one candidate string against the search term.

    Exactly one of ``canonical`` / ``alias`` should be the live candidate;
    the other should be omitted (or None).  The caller passes ``term``
    already lowercased + stripped; we lowercase the candidate defensively.

    Returns an int rank (lower = better) or None when there is no hit.
    """
    # Determine the candidate and its tier offsets.
    if canonical is not None and canonical.strip():
        cand = canonical.strip().lower()
        exact_rank = 0
        prefix_rank = 1
        substr_rank = 4
    elif alias is not None and alias.strip():
        cand = alias.strip().lower()
        exact_rank = 2
        prefix_rank = 3
        substr_rank = 5
    else:
        return None

    # Lowercase + strip term defensively (caller should already do this, but guard here).
    t = term.strip().lower()

    if cand == t:
        return exact_rank
    if cand.startswith(t):
        return prefix_rank
    if t in cand:
        return substr_rank
    return None


def merge_candidates(
    candidates: list[tuple[Hashable, int, str | None]],
) -> list[tuple[Hashable, int, str | None]]:
    """Deduplicate a ranked candidate list by entity key, keeping the best rank.

    ``candidates`` is a flat list of ``(entity_key, rank, matched_alias | None)``.
    The ``matched_alias`` is the alias string when the hit came from an alias
    row, or ``None`` when the hit came from the canonical field.

    For each entity key the row with the *lowest* rank wins.  When the winning
    row came from a canonical hit (rank 0/1/4) the ``matched_alias`` on the
    merged output is forced to ``None``; when it came from an alias hit (rank
    2/3/5) the alias string is preserved.

    Returns one row per entity, sorted by rank ascending.  Ties in rank retain
    a stable order (Python's sort is stable; the insertion order of first
    appearance is the secondary key when ranks are equal).
    """
    # {key: (rank, matched_alias)}
    best: dict[Hashable, tuple[int, str | None]] = {}

    for key, rank, alias in candidates:
        if key not in best or rank < best[key][0]:
            # Canonical hits (0/1/4) carry no alias hint.
            # Alias hits (2/3/5) carry the alias string.
            alias_out: str | None = alias if rank in (2, 3, 5) else None
            best[key] = (rank, alias_out)

    # Build output and sort by rank (stable: preserves insertion order on tie).
    merged = [(k, r, a) for k, (r, a) in best.items()]
    merged.sort(key=lambda row: row[1])
    return merged
