"""Compound deduplication service for the inject_compounds endpoint.

Canonicalizes submitted compound identifiers to PubChem CIDs, then removes:
1. Within-batch duplicates (same compound entered twice in different formats)
2. Cross-analysis duplicates (compound already in existing stage_1 results)

Falls back to lowercased string comparison when PubChem is unavailable.
"""
from __future__ import annotations

import logging

import httpx

from integrations.pubchem_compound import validate_compound  # noqa: F401 (patched in tests)

logger = logging.getLogger(__name__)


async def deduplicate_compounds(
    submitted: list[str],
    existing_ids: set[str],
) -> tuple[list[str], list[str]]:
    """Deduplicate submitted compound identifiers against each other and existing_ids.

    Each element of ``submitted`` may be a SMILES string, InChI string,
    InChIKey, PubChem CID, or compound name — any format accepted by
    ``validate_compound``.

    Strategy:
    1. Call PubChem for each input to get a canonical compound_id (UUID v5).
    2. If PubChem returns None for an input, fall back to lowercased/stripped
       string matching for that input (graceful degradation).
    3. First occurrence of each canonical key wins; subsequent occurrences are
       duplicates.
    4. Any compound whose canonical key is already in ``existing_ids`` is a
       duplicate regardless of batch position.

    Args:
        submitted: Raw compound identifiers as submitted by the caller.
        existing_ids: Set of compound_id strings already selected in the analysis
                      (from stage_1 results or any other prior selection).

    Returns:
        (unique_new, duplicates):
        - unique_new: the raw input strings that are genuinely new (deduplicated
          by canonical key, not already in existing_ids).
        - duplicates: the raw input strings that were removed.
    """
    unique_new: list[str] = []
    duplicates: list[str] = []

    # Tracks canonical keys seen so far within this batch.
    # For PubChem-resolved inputs: compound_id (UUID v5 string).
    # For fallback inputs: normalized raw string.
    seen_in_batch: set[str] = set()

    async with httpx.AsyncClient(timeout=20.0) as client:
        for raw in submitted:
            stripped = raw.strip()
            if not stripped:
                duplicates.append(raw)
                continue

            # Attempt PubChem canonicalization
            compound = None
            try:
                compound = await validate_compound(stripped, client)
            except Exception as exc:
                logger.warning(
                    "PubChem lookup failed for %r during dedup (fallback to string): %s",
                    stripped[:60],
                    exc,
                )

            if compound is not None:
                canonical_key = compound["compound_id"]
            else:
                # Fallback: use normalized string as canonical key
                canonical_key = stripped.lower()

            # Check against existing_ids (cross-analysis dedup)
            if canonical_key in existing_ids:
                duplicates.append(raw)
                continue

            # Check within-batch dedup
            if canonical_key in seen_in_batch:
                duplicates.append(raw)
                continue

            seen_in_batch.add(canonical_key)
            unique_new.append(raw)

    return unique_new, duplicates
