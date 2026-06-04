"""Unified DB-first input resolution service.

Shared resolution primitives for manual entity input (targets, and later compounds).
A single ``resolve_targets`` entry point that, for each raw input:

1. classifies it as a UniProt accession or a gene symbol,
2. looks it up FIRST in the canonical ``targets`` table (DB-first reuse — no network),
3. on a DB miss, enriches it via UniProt (one round-trip per novel input),
4. deduplicates within the batch and against caller-supplied ``existing_keys``,
5. persists newly enriched targets back to the ``targets`` table for future reuse.

This module is intentionally NOT wired into any HTTP endpoint yet — a later task
adapts the inject-targets router onto it. It mirrors the dict shape and helper
calls used by ``app.services.manual_inputs.inject_targets_service`` so the two stay
byte-compatible at the stage_3 contract level.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from analysis.stages.stage3_targets import _make_target_id
from integrations._retry import ServiceUnavailableError
from integrations.uniprot import validate_human_target
from sqlalchemy import func
from sqlmodel import select

from app.models.target import Target
from app.schemas.analysis import UNIPROT_ACCESSION_RE
from app.services import gene_symbols
from app.services.target_persist import persist_validated_targets

logger = logging.getLogger(__name__)


@dataclass
class LineFailure:
    line: int          # 1-based index in the submitted list
    input: str         # the raw string
    reason: str        # human-readable


@dataclass
class ResolveResult:
    valid: list[dict] = field(default_factory=list)        # canonical entity dicts
    failed: list[LineFailure] = field(default_factory=list)
    normalized: list[dict] = field(default_factory=list)   # [{"from","to"}]
    duplicates: list[str] = field(default_factory=list)    # raw inputs dropped as dups
    reused: int = 0                                         # DB cache hits (no provider call)
    enriched: int = 0                                       # provider round-trips made

    def to_payload(self) -> dict:
        return {
            "valid": self.valid,
            "failed": [f.__dict__ for f in self.failed],
            "normalized": self.normalized,
            "duplicates": self.duplicates,
            "reused": self.reused,
            "enriched": self.enriched,
        }


def _is_accession(value: str) -> bool:
    """Classify an already-stripped input as a UniProt accession vs a gene symbol.

    Matches the schema regex against the uppercased value so lowercase accessions
    (e.g. ``p04637``) still classify as accessions.
    """
    return bool(UNIPROT_ACCESSION_RE.match(value.upper()))


def _target_dict(
    gene: str | None,
    acc: str | None,
    protein: str | None,
    sources: list[str],
) -> dict:
    """Build the standard stage_3 target dict.

    ``target_id`` is the canonical UUID v5 when a UniProt accession is present;
    otherwise it is the symbol-only ``manual:{gene}`` form used for unrecognized
    inputs. The dict key for the accession is ``uniprot_id`` (the persist service
    maps it to the ``uniprot_accession`` column).
    """
    target_id = _make_target_id(acc, gene or "") if acc else f"manual:{gene}"
    return {
        "target_id": target_id,
        "gene_symbol": gene,
        "uniprot_id": acc,
        "protein_name": protein,
        "compound_ids": [],
        "sources": sources,
    }


def _uniprot_reason(msg: str, is_acc: bool) -> str:
    """Map a UniProt ``ValueError`` message to a concise human reason."""
    lowered = (msg or "").lower()
    if is_acc:
        if "invalid format" in lowered:
            return "invalid UniProt accession"
        return "UniProt accession not found"
    return "not found in UniProt / not a human protein"


async def _lookup_cached_target(
    *, is_acc: bool, key: str, session
) -> Target | None:
    """DB-first lookup against the canonical ``targets`` table.

    Accessions match on ``upper(uniprot_accession)``; symbols on
    ``upper(gene_symbol)``. ``key`` is the already-uppercased dedup key.
    """
    if is_acc:
        stmt = select(Target).where(func.upper(Target.uniprot_accession) == key)
    else:
        stmt = select(Target).where(func.upper(Target.gene_symbol) == key)
    result = await session.exec(stmt)
    return result.first()


async def resolve_targets(
    raw_inputs: list[str],
    *,
    lenient: bool,
    existing_keys: set[str],
    session,
) -> ResolveResult:
    """Resolve a batch of raw target inputs DB-first, then via UniProt.

    Args:
        raw_inputs: Raw strings (accessions or gene symbols), as submitted.
        lenient: When True, an unrecognized *symbol* is kept in ``valid`` flagged
            ``manual_unrecognized`` rather than dropped to ``failed``. Accessions
            are never kept on failure (they have no offline canonical form).
        existing_keys: Uppercased dedup keys already present (accessions and/or
            canonical gene symbols) — seeds the seen set so re-submissions dedup.
        session: Async SQLModel/SQLAlchemy session.

    Returns:
        A ``ResolveResult`` with the canonical dicts, per-line failures, offline
        normalizations, dropped duplicates, and reuse/enrichment counters.
    """
    result = ResolveResult()
    seen: set[str] = {k.upper() for k in (existing_keys or set())}
    to_persist: list[dict] = []

    for idx, raw in enumerate(raw_inputs, start=1):
        stripped = (raw or "").strip()
        if not stripped:
            result.failed.append(LineFailure(line=idx, input=raw, reason="empty line"))
            continue

        is_acc = _is_accession(stripped)

        # Classify + compute the dedup key (and offline-normalize symbols).
        if is_acc:
            key = stripped.upper()
        else:
            norm = gene_symbols.normalize(stripped)
            canonical = norm.canonical or stripped.upper()
            if canonical != stripped.upper():
                result.normalized.append({"from": stripped, "to": canonical})
            key = canonical.upper()

        # Within-batch + existing dedup.
        if key in seen:
            result.duplicates.append(raw)
            continue

        # DB-first reuse.
        cached = await _lookup_cached_target(is_acc=is_acc, key=key, session=session)
        if cached is not None:
            result.valid.append(
                _target_dict(
                    cached.gene_symbol,
                    cached.uniprot_accession,
                    cached.protein_name,
                    ["cache"],
                )
            )
            result.reused += 1
            seen.add(key)
            if cached.uniprot_accession:
                seen.add(cached.uniprot_accession.upper())
            if cached.gene_symbol:
                seen.add(cached.gene_symbol.upper())
            continue

        # DB miss → enrich via UniProt.
        try:
            info = await validate_human_target(
                gene_symbol=None if is_acc else key,
                uniprot_id=key if is_acc else None,
            )
        except ServiceUnavailableError:
            raise  # caller maps to HTTP 503
        except ValueError as exc:
            if lenient and not is_acc:
                # Lenient symbol path: keep + flag, never drop.
                td = _target_dict(key, None, None, ["manual_unrecognized"])
                result.valid.append(td)
                seen.add(key)
            else:
                result.failed.append(
                    LineFailure(
                        line=idx,
                        input=raw,
                        reason=_uniprot_reason(str(exc), is_acc),
                    )
                )
            continue

        td = _target_dict(
            info.gene_symbol,
            info.uniprot_accession,
            info.protein_name,
            ["manual"],
        )
        result.valid.append(td)
        to_persist.append(td)
        result.enriched += 1
        seen.add(key)
        if info.uniprot_accession:
            seen.add(info.uniprot_accession.upper())
        if info.gene_symbol:
            seen.add(info.gene_symbol.upper())

    # Persist only newly enriched targets that carry a UniProt accession.
    await persist_validated_targets(
        [t for t in to_persist if t.get("uniprot_id")], session
    )

    return result
