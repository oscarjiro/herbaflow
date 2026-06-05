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
import re
from dataclasses import dataclass, field

import httpx
from analysis.stages.stage3_targets import _make_target_id
from integrations._retry import ServiceUnavailableError
from integrations.pubchem_compound import validate_compound
from integrations.uniprot import validate_human_target
from sqlalchemy import func
from sqlmodel import select

from app.models.compound import Compound
from app.models.target import Target
from app.schemas.analysis import UNIPROT_ACCESSION_RE
from app.services import gene_symbols
from app.services.canonicalize import make_compound_id
from app.services.compound_persist import persist_validated_compounds
from app.services.target_persist import persist_validated_targets

logger = logging.getLogger(__name__)

# A standard InChIKey: 14 block / 10 block / 1 char (e.g. BSYNRYMUTXBXSQ-UHFFFAOYSA-N).
_INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


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


@dataclass
class ScopeRequest:
    """One named target scope to resolve as part of a shared union."""

    name: str
    inputs: list[str]
    lenient: bool = False


async def resolve_target_scopes(
    scopes: list[ScopeRequest],
    *,
    session,
) -> dict[str, ResolveResult]:
    """Resolve several named target scopes against a SHARED union.

    Each unique target (by canonical key) is looked up DB-first and, on a miss,
    enriched via UniProt EXACTLY ONCE across all scopes — the resolved (or failed)
    outcome is then fanned back out to every scope that asked for it. A symbol that
    UniProt rejects is kept-and-flagged in a lenient scope and dropped to ``failed``
    in a strict one: the keep/drop decision is per-scope, but the resolution work
    (DB lookup + UniProt round-trip) is shared, so a target appearing in both the
    compound-side and disease-side lists costs a single provider call.

    Args:
        scopes: Named scopes, each with its raw inputs and lenient flag.
        session: Async SQLModel/SQLAlchemy session.

    Returns:
        ``{scope_name: ResolveResult}`` — one result per scope, in the same dict
        shape as ``resolve_targets``. Newly enriched targets carrying a UniProt
        accession are persisted once.
    """
    results: dict[str, ResolveResult] = {s.name: ResolveResult() for s in scopes}

    # 1. Per-scope preprocess: classify, offline-normalize, in-scope dedup.
    #    asks[name] = list of (line, raw, key, is_acc) in input order.
    asks: dict[str, list[tuple[int, str, str, bool]]] = {}
    for s in scopes:
        scope_asks: list[tuple[int, str, str, bool]] = []
        seen: set[str] = set()
        for idx, raw in enumerate(s.inputs, start=1):
            stripped = (raw or "").strip()
            if not stripped:
                results[s.name].failed.append(
                    LineFailure(line=idx, input=raw, reason="empty line")
                )
                continue
            is_acc = _is_accession(stripped)
            if is_acc:
                key = stripped.upper()
            else:
                norm = gene_symbols.normalize(stripped)
                canonical = norm.canonical or stripped.upper()
                if canonical != stripped.upper():
                    results[s.name].normalized.append({"from": stripped, "to": canonical})
                key = canonical.upper()
            if key in seen:
                results[s.name].duplicates.append(raw)
                continue
            seen.add(key)
            scope_asks.append((idx, raw, key, is_acc))
        asks[s.name] = scope_asks

    # 2. Union of unique keys across all scopes (first-seen order).
    union: dict[str, bool] = {}
    for s in scopes:
        for _idx, _raw, key, is_acc in asks[s.name]:
            union.setdefault(key, is_acc)

    # 3. Resolve each unique key ONCE: DB-first, then UniProt on a miss.
    resolved: dict[str, dict] = {}
    origin: dict[str, str] = {}          # key -> "reused" | "enriched"
    failed_reason: dict[str, str] = {}
    to_persist: list[dict] = []
    for key, is_acc in union.items():
        cached = await _lookup_cached_target(is_acc=is_acc, key=key, session=session)
        if cached is not None:
            resolved[key] = _target_dict(
                cached.gene_symbol, cached.uniprot_accession, cached.protein_name, ["cache"]
            )
            origin[key] = "reused"
            continue
        try:
            info = await validate_human_target(
                gene_symbol=None if is_acc else key,
                uniprot_id=key if is_acc else None,
            )
        except ServiceUnavailableError:
            raise  # caller maps to HTTP 503
        except ValueError as exc:
            failed_reason[key] = _uniprot_reason(str(exc), is_acc)
            continue
        td = _target_dict(info.gene_symbol, info.uniprot_accession, info.protein_name, ["manual"])
        resolved[key] = td
        origin[key] = "enriched"
        to_persist.append(td)

    await persist_validated_targets([t for t in to_persist if t.get("uniprot_id")], session)

    # 4. Fan out per scope (per-scope lenient keep/drop on a shared failure).
    for s in scopes:
        res = results[s.name]
        for idx, raw, key, is_acc in asks[s.name]:
            if key in resolved:
                res.valid.append(dict(resolved[key]))
                if origin[key] == "reused":
                    res.reused += 1
                else:
                    res.enriched += 1
            elif s.lenient and not is_acc:
                res.valid.append(_target_dict(key, None, None, ["manual_unrecognized"]))
            else:
                res.failed.append(
                    LineFailure(
                        line=idx, input=raw,
                        reason=failed_reason.get(key, "could not be resolved"),
                    )
                )

    return results


# ---------------------------------------------------------------------------
# Compound resolution
# ---------------------------------------------------------------------------
def _classify_compound(stripped: str) -> str:
    """Classify an already-stripped compound input.

    Returns one of ``"inchikey"`` (DB-only), ``"cid"`` (all-digits PubChem CID,
    DB-only), or ``"structure"`` (SMILES / InChI / name → PubChem round-trip).
    """
    if _INCHIKEY_RE.match(stripped.upper()):
        return "inchikey"
    if stripped.isdigit():
        return "cid"
    return "structure"


def _compound_cache_dict(row: Compound) -> dict:
    """Build a stage_1-compatible compound dict from a cached ``Compound`` row.

    Mirrors the key shape ``validate_compound`` returns so downstream stages stay
    happy, tagged ``sources=["cache"]`` (mirrors how ``_target_dict`` marks a hit).
    """
    return {
        "compound_id": row.compound_id,
        "canonical_key": row.canonical_key,
        "pubchem_cid": row.pubchem_cid,
        "inchikey": row.inchi_key,
        "iupac_name": row.canonical_name,
        "molecular_formula": row.molecular_formula,
        "molecular_weight": row.molecular_weight,
        "canonical_name": row.canonical_name,
        "plant_ids": [],
        "adme_pass": None,
        "is_np_exception": False,
        "is_pains_positive": bool(row.is_pains_positive),
        "logp": row.logp,
        "tpsa": row.tpsa,
        "hbond_donors": row.hbond_donors,
        "hbond_acceptors": row.hbond_acceptors,
        "np_likeness_score": row.np_likeness_score,
        "rotatable_bonds": row.rotatable_bonds,
        "mw": row.molecular_weight,
        "xlogp": row.logp,
        "hbd": row.hbond_donors,
        "hba": row.hbond_acceptors,
        "sources": ["cache"],
    }


async def _lookup_cached_compound(*, kind: str, key: str, session) -> Compound | None:
    """DB-first lookup against the canonical ``compounds`` table.

    ``inchikey`` matches on ``upper(inchi_key)``; ``cid`` matches on
    ``pubchem_cid`` (exact, stored as a string).
    """
    if kind == "inchikey":
        stmt = select(Compound).where(func.upper(Compound.inchi_key) == key)
    else:
        stmt = select(Compound).where(Compound.pubchem_cid == key)
    result = await session.exec(stmt)
    return result.first()


async def _lookup_compound_by_id(*, compound_id: str, session) -> Compound | None:
    """Look up an already-resolved compound by its canonical id (DB-first persist check)."""
    stmt = select(Compound).where(Compound.compound_id == compound_id)
    result = await session.exec(stmt)
    return result.first()


async def resolve_compounds(
    raw_inputs: list[str],
    *,
    existing_keys: set[str],
    session,
    client: httpx.AsyncClient,
) -> ResolveResult:
    """Resolve a batch of raw compound inputs DB-first, then via PubChem.

    Per input (1-based index):

    - **InChIKey** (``^[A-Z]{14}-[A-Z]{10}-[A-Z]$``, case-insensitive) → DB-only:
      look up by ``upper(inchi_key)``. Hit → reuse (no PubChem); miss → failed.
    - **all-digits CID** → DB-only: look up by ``pubchem_cid``. Hit → reuse; miss
      → failed.
    - **else (SMILES / InChI / name)** → ``validate_compound`` EXACTLY ONCE. A dict
      is BOTH the ``valid`` entry and the persist payload; ``None`` → failed.

    Dedup is on the canonical ``compound_id`` (a UUID string, compared exactly)
    against ``existing_keys`` and within the batch. A structure also dedups on its
    raw text so a byte-identical repeat never triggers a second PubChem call.
    ``reused`` counts DB cache hits (InChIKey/CID hit, or a structure whose
    resolved compound is already cached); ``enriched`` counts structures whose
    PubChem round-trip resolved a NEW, not-yet-cached compound.

    Args:
        raw_inputs: Raw compound strings (InChIKey, CID, SMILES, InChI, or name).
        existing_keys: ``compound_id`` strings already present — seeds the seen set.
        session: Async SQLModel/SQLAlchemy session.
        client: Shared ``httpx.AsyncClient`` for PubChem lookups.

    Returns:
        A ``ResolveResult`` with the canonical dicts, per-line failures, dropped
        duplicates, and reuse/enrichment counters. ``normalized`` is unused here.
    """
    result = ResolveResult()
    # compound_id dedup keys are UUID strings — compared exactly (no upper()).
    seen: set[str] = set(existing_keys or set())
    # Tracks raw structure text already PubChem-resolved this batch, so a
    # byte-identical repeat dedups without a second validate_compound call.
    seen_structures: set[str] = set()
    to_persist: list[dict] = []

    for idx, raw in enumerate(raw_inputs, start=1):
        stripped = (raw or "").strip()
        if not stripped:
            result.failed.append(LineFailure(line=idx, input=raw, reason="empty line"))
            continue

        kind = _classify_compound(stripped)

        # --- InChIKey: DB-only, compute id up front to dedup before the DB call.
        if kind == "inchikey":
            key = stripped.upper()
            compound_id = make_compound_id(key)
            if compound_id in seen:
                result.duplicates.append(raw)
                continue
            cached = await _lookup_cached_compound(kind="inchikey", key=key, session=session)
            if cached is not None:
                result.valid.append(_compound_cache_dict(cached))
                result.reused += 1
                seen.add(cached.compound_id)
                continue
            result.failed.append(
                LineFailure(
                    line=idx,
                    input=raw,
                    reason="not in cache — paste the structure to resolve via PubChem",
                )
            )
            continue

        # --- CID: DB-only; the canonical id is unknown until the row is found.
        if kind == "cid":
            cached = await _lookup_cached_compound(kind="cid", key=stripped, session=session)
            if cached is not None:
                if cached.compound_id in seen:
                    result.duplicates.append(raw)
                    continue
                result.valid.append(_compound_cache_dict(cached))
                result.reused += 1
                seen.add(cached.compound_id)
                continue
            result.failed.append(
                LineFailure(
                    line=idx,
                    input=raw,
                    reason="not in cache — paste the structure to resolve via PubChem",
                )
            )
            continue

        # --- Structure (SMILES / InChI / name): one PubChem round-trip, max.
        if stripped in seen_structures:
            result.duplicates.append(raw)
            continue

        info = await validate_compound(stripped, client)
        if info is None:
            result.failed.append(
                LineFailure(line=idx, input=raw, reason="not found in PubChem")
            )
            continue

        seen_structures.add(stripped)
        compound_id = info["compound_id"]
        if compound_id in seen:
            # Resolves to a compound already selected this batch / in existing_keys.
            result.duplicates.append(raw)
            continue
        seen.add(compound_id)

        # DB-first persist check: if already cached, this is reuse, not enrichment.
        existing_row = await _lookup_compound_by_id(compound_id=compound_id, session=session)
        if existing_row is not None:
            result.reused += 1
        else:
            result.enriched += 1
        # The single resolved dict is BOTH the valid entry and the persist payload.
        result.valid.append(info)
        to_persist.append(info)

    # Persist only structure-resolved compounds that carry a PubChem CID.
    await persist_validated_compounds(
        [c for c in to_persist if c.get("pubchem_cid")], session
    )

    return result
