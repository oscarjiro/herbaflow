"""Target DB persistence service.

Persists UniProt-validated targets to the ``targets`` table after successful
manual target injection. Symmetric to ``compound_persist``: uses SELECT-then-INSERT
semantics to avoid duplicate key errors — effectively an upsert that skips
already-persisted rows.

Design decisions:
- Only targets with a confirmed ``uniprot_id`` (UniProt accession) are persisted.
  skip_validation fast-path targets (``target_id="manual:{GENE}"``, no accession)
  are intentionally NOT persisted — they are unvalidated gene symbols and must not
  pollute the canonical ``targets`` table.
- No CompoundTarget or DiseaseTarget link rows are created here — manual targets
  carry no compound/disease associations.
- DB errors are non-fatal: a warning is logged and 0 is returned so the
  inject_targets endpoint continues and returns a valid response.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Iterable

from sqlmodel import select

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.target import Target
from app.services.canonicalize import target_canonical_key

logger = logging.getLogger(__name__)


async def persist_canonical_target(
    targets: Iterable[Target],
    session: AsyncSession,
) -> int:
    """Insert pre-built ``Target`` rows that are not already present.

    Canonical persist primitive: for each ``Target``, SELECT by ``target_id``;
    if absent, ``session.add`` it and count it; if present, skip. Creates no
    CompoundTarget / DiseaseTarget / PlantCompound link rows and does NOT commit
    — the caller controls commit granularity.

    Args:
        targets: Pre-built ``Target`` instances to insert if absent.
        session: Async SQLModel/SQLAlchemy session.

    Returns:
        Number of target rows added to the session (already-present rows skipped).
    """
    inserted = 0
    for target in targets:
        existing = (await session.exec(
            select(Target).where(Target.target_id == target.target_id)
        )).one_or_none()
        if existing is not None:
            continue  # already persisted — skip (ON CONFLICT DO NOTHING semantics)
        session.add(target)
        inserted += 1
    return inserted


async def persist_validated_targets(
    validated_targets: list[dict],
    session: AsyncSession,
) -> int:
    """Persist targets that have a UniProt accession to the targets table.

    Args:
        validated_targets: List of target dicts as produced by inject_targets after
            UniProt validation. Each dict must have ``target_id`` and ``gene_symbol``;
            ``uniprot_id`` and ``protein_name`` are optional. Entries with a falsy
            ``uniprot_id`` (skip_validation fast-path) are skipped.
        session: Async SQLModel/SQLAlchemy session. The caller provides an open
            session; this function commits if it inserts any rows.

    Returns:
        Number of target rows actually inserted (0 if all already existed, all were
        unvalidated, or on DB error).
    """
    try:
        return await _do_persist(validated_targets, session)
    except Exception as exc:
        logger.warning(
            "Target persistence failed — proceeding without persist: %s",
            exc,
            exc_info=True,
        )
        return 0


async def _do_persist(
    validated_targets: list[dict],
    session: AsyncSession,
) -> int:
    """Inner implementation — raises on DB error (caller handles)."""
    now = datetime.utcnow()

    targets: list[Target] = []
    for t in validated_targets:
        # Only persist targets that were validated against UniProt (have an accession)
        uniprot_accession = t.get("uniprot_id")
        if not uniprot_accession:
            continue

        gene_symbol = (t.get("gene_symbol") or "").upper() or None

        targets.append(
            Target(
                target_id=t["target_id"],
                canonical_key=target_canonical_key(uniprot_accession),
                gene_symbol=gene_symbol,
                uniprot_accession=uniprot_accession,
                protein_name=t.get("protein_name"),
                retrieved_at=now,
            )
        )

    inserted = await persist_canonical_target(targets, session)

    if inserted > 0:
        await session.commit()

    return inserted
