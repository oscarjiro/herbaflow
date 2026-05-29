"""Target DB caching service.

Persists UniProt-validated targets to the ``targets`` table after successful
manual target injection. Symmetric to ``compound_cache``: uses SELECT-then-INSERT
semantics to avoid duplicate key errors — effectively an upsert that skips
already-cached rows.

Design decisions (mirrors compound_cache §2.6):
- Only targets with a confirmed ``uniprot_id`` (UniProt accession) are persisted.
  skip_validation fast-path targets (``target_id="manual:{GENE}"``, no accession)
  are intentionally NOT cached — they are unvalidated gene symbols and must not
  pollute the canonical ``targets`` table.
- No CompoundTarget or DiseaseTarget link rows are created here — manual targets
  carry no compound/disease associations.
- DB errors are non-fatal: a warning is logged and 0 is returned so the
  inject_targets endpoint continues and returns a valid response.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import select

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.target import Target

logger = logging.getLogger(__name__)


async def cache_validated_targets(
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
        return await _do_cache(validated_targets, session)
    except Exception as exc:
        logger.warning(
            "Target caching failed — proceeding without cache: %s",
            exc,
            exc_info=True,
        )
        return 0


async def _do_cache(
    validated_targets: list[dict],
    session: AsyncSession,
) -> int:
    """Inner implementation — raises on DB error (caller handles)."""
    now = datetime.utcnow()
    inserted = 0

    for t in validated_targets:
        # Only persist targets that were validated against UniProt (have an accession)
        uniprot_accession = t.get("uniprot_id")
        if not uniprot_accession:
            continue

        target_id: str = t["target_id"]

        # Check whether this target is already cached
        existing = (await session.exec(
            select(Target).where(Target.target_id == target_id)
        )).one_or_none()
        if existing is not None:
            continue  # already cached — skip (ON CONFLICT DO NOTHING semantics)

        gene_symbol = (t.get("gene_symbol") or "").upper() or None

        session.add(
            Target(
                target_id=target_id,
                canonical_key=f"uniprot:{uniprot_accession}",
                gene_symbol=gene_symbol,
                uniprot_accession=uniprot_accession,
                protein_name=t.get("protein_name"),
                organism_tax_id=9606,
                retrieved_at=now,
            )
        )
        inserted += 1

    if inserted > 0:
        await session.commit()

    return inserted
