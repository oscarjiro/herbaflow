"""Compound DB persistence service.

Persists canonicalized compounds (those with a confirmed PubChem CID) to the
``compounds`` table after successful batch validation. Uses SELECT-then-INSERT
semantics to avoid duplicate key errors — effectively an upsert that skips
already-persisted rows.

Design decisions:
- Only compounds with a ``pubchem_cid`` are persisted — SMILES-only compounds
  (no CID) are allowed in the pipeline but are NOT persisted.
- No plant–compound or disease–compound links are created here.
- DB errors are non-fatal: a warning is logged and 0 is returned so that the
  inject_compounds endpoint continues and returns a valid response.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable

from sqlmodel import select

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.compound import Compound
from app.repositories.analysis_repo import now_utc

logger = logging.getLogger(__name__)


async def persist_canonical_compound(
    compounds: Iterable[Compound],
    session: AsyncSession,
) -> int:
    """Insert pre-built ``Compound`` rows that are not already present.

    Canonical persist primitive: for each ``Compound``, SELECT by ``compound_id``;
    if absent, ``session.add`` it and count it; if present, skip. Creates no
    PlantCompound / DiseaseCompound link rows and does NOT commit — the caller
    controls commit granularity.

    Args:
        compounds: Pre-built ``Compound`` instances to insert if absent.
        session: Async SQLModel/SQLAlchemy session.

    Returns:
        Number of compound rows added to the session (already-present rows skipped).
    """
    inserted = 0
    for compound in compounds:
        result = await session.exec(
            select(Compound).where(Compound.compound_id == compound.compound_id)
        )
        existing = result.first()
        if existing is not None:
            continue  # already persisted — skip (ON CONFLICT DO NOTHING semantics)
        session.add(compound)
        inserted += 1
    return inserted


async def persist_validated_compounds(
    validated_compounds: list[dict],
    session: AsyncSession,
) -> int:
    """Persist compounds that have a valid PubChem CID to the compounds table.

    Args:
        validated_compounds: List of compound dicts as returned by
            ``validate_compounds_batch``. Each dict must have at minimum
            ``compound_id``, ``canonical_name``, and ``pubchem_cid`` keys.
        session: Async SQLModel/SQLAlchemy session.  The caller is responsible
            for providing an open session; this function commits if it inserts
            any rows.

    Returns:
        Number of compound rows actually inserted (0 if all already existed or
        all had no CID, or on DB error).
    """
    try:
        return await _do_persist(validated_compounds, session)
    except Exception as exc:
        logger.warning(
            "Compound persistence failed — proceeding without persist: %s",
            exc,
            exc_info=True,
        )
        return 0


async def _do_persist(
    validated_compounds: list[dict],
    session: AsyncSession,
) -> int:
    """Inner implementation — raises on DB error (caller handles)."""
    now = now_utc()

    compounds: list[Compound] = []
    for c in validated_compounds:
        # Only persist compounds that were successfully canonicalized via PubChem
        if not c.get("pubchem_cid"):
            continue

        canonical_key = c["canonical_key"]  # always set by the canonicalization core

        compounds.append(
            Compound(
                compound_id=c["compound_id"],
                canonical_key=canonical_key,
                canonical_name=c["canonical_name"],
                pubchem_cid=c.get("pubchem_cid"),
                smiles=c.get("smiles"),
                inchi_key=c.get("inchikey"),
                molecular_weight=c.get("molecular_weight"),
                logp=c.get("logp"),
                tpsa=c.get("tpsa"),
                hbond_donors=c.get("hbond_donors"),
                hbond_acceptors=c.get("hbond_acceptors"),
                rotatable_bonds=c.get("rotatable_bonds"),
                np_likeness_score=c.get("np_likeness_score"),
                is_pains_positive=bool(c.get("is_pains_positive", False)),
                retrieved_at=now,
            )
        )

    inserted = await persist_canonical_compound(compounds, session)

    if inserted > 0:
        await session.commit()

    return inserted
