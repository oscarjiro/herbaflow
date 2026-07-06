"""Shared gene-symbol helpers — one home for "distinct non-null gene_symbol, first-seen order".

Stage 6 needs the deduped ROWS (to keep target_id/uniprot_accession); Stage 8 needs the list of
symbols. Both derive from the same dedupe so the rule lives once (B-DUP-3).
"""

from __future__ import annotations

from typing import Any


def distinct_gene_symbol_rows(
    rows: list[dict[str, Any]], key: str = "gene_symbol"
) -> list[dict[str, Any]]:
    """Rows with a distinct non-null ``key`` value, first occurrence wins."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        g = row.get(key)
        if g and g not in seen:
            seen.add(g)
            out.append(row)
    return out


def distinct_gene_symbols(rows: list[dict[str, Any]], key: str = "gene_symbol") -> list[str]:
    """Distinct non-null gene symbols from ``rows`` (preserves first-seen order)."""
    return [r[key] for r in distinct_gene_symbol_rows(rows, key)]


def target_display_name(
    gene_symbol: str | None,
    uniprot_accession: str | None,
    target_id: str | None = None,
    protein_name: str | None = None,
) -> str | None:
    """The single home for a target's display name.

    Fallback order: gene_symbol -> protein_name -> uniprot_accession -> target_id. Sites that
    do not carry a ``protein_name`` (every site except the edit-layer target-add builder) leave it
    ``None`` so the effective order is gene_symbol -> uniprot_accession -> target_id; sites that do
    not carry a ``target_id`` leave it ``None`` so the effective order stops at uniprot_accession.
    This keeps each caller's existing fallback exactly while removing the copy-paste (B2/B5).
    """
    return gene_symbol or protein_name or uniprot_accession or target_id
