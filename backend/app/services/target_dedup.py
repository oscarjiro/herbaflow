"""Target deduplication service for inject_targets endpoint.

Canonicalizes submitted target identifiers to UniProt accessions, then removes:
1. Within-batch duplicates (same protein entered as both gene symbol and accession)
2. Cross-analysis duplicates (target already in existing stage_3 results)

Falls back to lowercased gene_symbol when UniProt is unavailable.
"""
from __future__ import annotations

import logging

from integrations._retry import ServiceUnavailableError
from integrations.uniprot import validate_human_target

logger = logging.getLogger(__name__)


async def deduplicate_targets(
    submitted: list[dict],
    existing_ids: set[str],
) -> tuple[list[dict], list[str]]:
    """Deduplicate submitted targets against each other and existing_ids.

    Each element of ``submitted`` is a dict with optional keys:
      - ``gene_symbol``: HGNC gene symbol (e.g. "TP53")
      - ``uniprot_id``: UniProt accession (e.g. "P04637")

    Strategy:
    1. Call UniProt for each input to get a canonical accession.
    2. If UniProt is unavailable (ServiceUnavailableError) → fall back to
       lowercased gene_symbol for dedup (graceful degradation, never raises).
    3. If no gene_symbol or uniprot_id present → include as-is (no dedup key).
    4. First occurrence of each canonical key wins; later occurrences are
       duplicates.
    5. Any target whose canonical key is already in ``existing_ids`` is a
       duplicate regardless of batch position.

    Args:
        submitted:    List of target dicts, each with gene_symbol and/or uniprot_id.
        existing_ids: Set of UniProt accessions already selected in this analysis
                      (e.g. from existing stage_3 results).

    Returns:
        (unique_new, duplicates):
        - unique_new:  Dicts that are genuinely new after deduplication.
        - duplicates:  Human-readable labels (gene_symbol or uniprot_id) for
                       the entries that were removed.
    """
    unique_new: list[dict] = []
    duplicates: list[str] = []

    # Canonical keys seen within this batch (UniProt accession or lowercased fallback)
    seen_in_batch: set[str] = set()

    for entry in submitted:
        gene_symbol = (entry.get("gene_symbol") or "").strip()
        uniprot_id = (entry.get("uniprot_id") or "").strip()

        # Label used in duplicate_names: prefer uniprot_id if that's what was submitted
        label = uniprot_id or gene_symbol or repr(entry)

        if not gene_symbol and not uniprot_id:
            # No canonicalization possible — include as-is with no dedup key
            unique_new.append(entry)
            continue

        canonical_key: str | None = None

        try:
            info = await validate_human_target(
                gene_symbol=gene_symbol or None,
                uniprot_id=uniprot_id or None,
            )
            canonical_key = info.uniprot_accession.upper()
        except ServiceUnavailableError:
            # UniPort down — fall back to uppercased gene_symbol for dedup
            if gene_symbol:
                canonical_key = gene_symbol.upper()
            else:
                # Only accession provided but UniProt is down — use uppercased accession
                canonical_key = uniprot_id.upper()
            logger.warning(
                "UniProt unavailable during dedup for %r — using fallback key %r",
                label,
                canonical_key,
            )
        except ValueError:
            # Validation error (not found, not human) — include as-is so the
            # endpoint can put it in the failed list rather than silently dropping it
            unique_new.append(entry)
            continue
        except Exception as exc:
            logger.warning(
                "Unexpected error during UniProt dedup lookup for %r: %s", label, exc
            )
            unique_new.append(entry)
            continue

        # Cross-analysis dedup
        if canonical_key in existing_ids:
            duplicates.append(label)
            continue

        # Within-batch dedup
        if canonical_key in seen_in_batch:
            duplicates.append(label)
            continue

        seen_in_batch.add(canonical_key)
        unique_new.append(entry)

    return unique_new, duplicates
