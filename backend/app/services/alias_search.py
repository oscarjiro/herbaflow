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

from collections.abc import Callable, Hashable

# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #


def like_escape(term: str) -> str:
    r"""Escape SQL ``LIKE`` / ``ILIKE`` wildcards in a user-typed search term.

    A raw ``%`` or ``_`` in the term must match *literally* rather than act as a
    wildcard, so a search for ``"a_b"`` does not silently also match ``"aXb"``.
    Escape the escape character first, then ``%`` and ``_``. Callers wrap the
    result in ``f"%{like_escape(q)}%"`` and pass ``escape="\\"`` to ``.ilike(...)``.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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
    appearance is the secondary key when ranks are equal). This function
    guarantees only the rank ordering; the service caller applies a secondary
    canonical-name sort for the final display order.
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


def rank_and_page_search[E](
    rows: list[tuple[E, str | None]],
    term: str,
    *,
    name_of: Callable[[E], str | None],
    id_of: Callable[[E], Hashable],
    limit: int,
    offset: int,
) -> list[tuple[E, str | None]]:
    """Rank alias-search candidate rows and return the paged ``(entity, matched_alias)`` list.

    The single home for the plant/disease catalog search body: given ``rows`` (``(entity, alias)``
    tuples from a repository ``search_candidates`` read) and the already stripped+lowercased
    ``term``, rank canonical then alias matches, dedupe per entity keeping the best rank, sort by
    (rank, canonical name), and page. An empty ``term`` returns the entities in their incoming
    order (the repo already name-sorts them), one per entity, ``matched_alias`` ``None``. Callers
    supply ``name_of``/``id_of`` accessors and build their own Read DTO + count map around the
    result, so this stays pure (no DB, no DTO, no I/O).
    """
    if not term:
        return [(entity, None) for entity, _ in rows[offset : offset + limit]]

    candidates: list[tuple[Hashable, int, str | None]] = []
    for entity, alias in rows:
        r = rank_match(term, canonical=name_of(entity))
        if r is not None:
            candidates.append((id_of(entity), r, None))
            continue
        r = rank_match(term, alias=alias)
        if r is not None:
            candidates.append((id_of(entity), r, alias))

    merged = merge_candidates(candidates)
    entity_by_id: dict[Hashable, E] = {id_of(entity): entity for entity, _ in rows}

    def sort_key(row: tuple[Hashable, int, str | None]) -> tuple[int, str]:
        key, rank, _alias = row
        name = (name_of(entity_by_id[key]) or "").lower()
        return (rank, name)

    merged.sort(key=sort_key)
    page = merged[offset : offset + limit]
    return [(entity_by_id[key], matched_alias) for key, _rank, matched_alias in page]
