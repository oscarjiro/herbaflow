"""Entity-count caps (RS.2) — the single home reused at pre-run entry and in-stage adds.

Methodology caps the UNIQUE, validated, deduped, canonicalized counts per run:
compounds <= 2000, targets <= 5000, plants <= 20. All three ceilings are sourced from
the shared contract via ``app.contracts`` accessors (one source of truth — never re-hardcoded).

No silent truncation: overflow raises :class:`EntityCapExceeded` carrying the cap and the
current count so callers can surface "cap / current". The pass condition is
``current + adding <= cap`` (exactly the cap is allowed).
"""

from __future__ import annotations

from app import contracts


class EntityCapExceeded(Exception):
    """Adding ``adding`` entities to ``current`` would exceed the run cap for ``entity``."""

    def __init__(self, entity: str, cap: int, current: int, adding: int) -> None:
        self.entity, self.cap, self.current, self.adding = entity, cap, current, adding
        super().__init__(f"{entity} cap {cap} exceeded: have {current}, adding {adding}")


def _caps() -> dict[str, int]:
    return {
        "compound": contracts.max_compounds(),
        "target": contracts.max_targets(),
        "plant": contracts.max_plants(),
    }


def check_entity_cap(entity: str, *, current: int, adding: int) -> None:
    """Raise :class:`EntityCapExceeded` if ``current + adding`` exceeds the cap for ``entity``.

    ``entity`` is one of ``"compound"``, ``"target"``, ``"plant"``. An unknown entity raises
    ``KeyError`` (internal misuse, not a user-facing condition).
    """
    cap = _caps()[entity]
    if current + adding > cap:
        raise EntityCapExceeded(entity, cap, current, adding)
