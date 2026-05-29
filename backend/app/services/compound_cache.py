"""Compound DB caching service.

Persists canonicalized compounds (those with a confirmed PubChem CID) to the
``compounds`` table after successful batch validation. Uses SELECT-then-INSERT
semantics to avoid duplicate key errors — effectively an upsert that skips
already-cached rows.

Design decisions:
- Only compounds with a ``pubchem_cid`` are persisted — SMILES-only compounds
  (no CID) are allowed in the pipeline but are NOT cached.
- No plant–compound or disease–compound links are created here.
- DB errors are non-fatal: a warning is logged and 0 is returned so that the
  inject_compounds endpoint continues and returns a valid response.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import select

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.compound import Compound

logger = logging.getLogger(__name__)


async def cache_validated_compounds(
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
        return await _do_cache(validated_compounds, session)
    except Exception as exc:
        logger.warning(
            "Compound caching failed — proceeding without cache: %s",
            exc,
            exc_info=True,
        )
        return 0


async def _do_cache(
    validated_compounds: list[dict],
    session: AsyncSession,
) -> int:
    """Inner implementation — raises on DB error (caller handles)."""
    now = datetime.utcnow()
    inserted = 0

    for c in validated_compounds:
        # Only persist compounds that were successfully canonicalized via PubChem
        if not c.get("pubchem_cid"):
            continue

        compound_id: str = c["compound_id"]

        # Check whether this compound is already cached
        result = await session.exec(
            select(Compound).where(Compound.compound_id == compound_id)
        )
        existing = result.first()
        if existing is not None:
            continue  # already cached — skip (upsert/ON CONFLICT DO NOTHING semantics)

        canonical_key = c.get("canonical_key") or f"pubchem:{c['pubchem_cid']}"

        session.add(
            Compound(
                compound_id=compound_id,
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
        inserted += 1

    if inserted > 0:
        await session.commit()

    return inserted
