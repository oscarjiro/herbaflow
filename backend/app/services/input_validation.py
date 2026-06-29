"""Manual-input resolution: classify -> identity -> DB-first -> enrich -> persist."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.clock import now_utc
from app.integrations.uniprot import UniProtReason, UniProtRecord, UniProtResolution
from app.schemas.compound import CompoundInput, FailedInput, ResolvedCompound
from app.schemas.target import ResolvedTarget, TargetInput
from app.services import canonical, gene_symbols, structure

logger = logging.getLogger("herbaflow.resolution")


@dataclass(frozen=True)
class AccessionResolution:
    """Result of accession→target resolution: the target, or why it could not resolve."""

    target: ResolvedTarget | None
    reason: UniProtReason | None  # set iff target is None


# Official UniProtKB accession grammar (https://www.uniprot.org/help/accession_numbers).
# Used to classify a typeless manual target as an accession vs a gene symbol. A loose
# "[A-Z0-9]{6,10}" wrongly matched real human gene symbols shaped like accessions (e.g.
# TAS2R38), routing them to an accession lookup that 400s and falsely reports "not human";
# the strict grammar lets such symbols fall through to the gene-symbol resolver.
_ACCESSION_RE = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)

# A UniProt isoform identifier is an entry's accession plus a "-<n>" suffix (e.g. P00533-2).
# Identity canonicalizes on the entry's primary accession and there is no separate UniProt entry
# for an isoform, so resolution strips the suffix and resolves the base accession's entry.
_ISOFORM_RE = re.compile(r"^(.+)-[0-9]+$")


def _accession_base(token: str) -> str:
    """Return the base accession of a UniProt isoform id (P00533-2 -> P00533); else the token."""
    m = _ISOFORM_RE.match(token)
    if m and _ACCESSION_RE.match(m.group(1)):
        return m.group(1)
    return token


def _is_accession_shaped(token: str) -> bool:
    """True if a typeless token looks like a UniProt accession (allowing an isoform suffix)."""
    return bool(_ACCESSION_RE.match(token) or _ACCESSION_RE.match(_accession_base(token)))


# Honest accession-failure wording, distinguishing the two causes the UniProt client already
# separates: a 400 (not a resolvable UniProt query at all) vs a valid query with no human hit.
_ACCESSION_FAIL_MSG = {
    UniProtReason.INVALID_ID: "not a UniProt accession",
    UniProtReason.NO_HUMAN_RECORD: "no human (9606) UniProt record",
}


@dataclass
class _CompoundWork:
    """One distinct, format-valid identity to resolve (phased batch-resolve dedup unit)."""

    value: str  # original input value of the first occurrence (for FailedInput.value)
    line: int  # 1-based line of the first occurrence (for FailedInput.line)
    inchikey: str
    smiles: str | None  # canonical SMILES for SMILES-derived inputs; None for bare InChIKey


async def resolve_compounds(
    inputs: list[CompoundInput], repo: Any, pubchem: Any
) -> tuple[list[ResolvedCompound], list[FailedInput]]:
    """Resolve manual compounds: classify -> dedup -> DB-first -> PubChem -> persist.

    Phased so identical inputs resolve once and only the pure-network calls run concurrently —
    a single ``AsyncSession`` cannot run concurrent statements, so all DB reads/writes stay
    serial; only ``pubchem.fetch_by_inchikey`` fans out via ``asyncio.gather`` (bounded by
    PubChem's own throttle/semaphore):

    0. classify + dedup: SMILES inputs are grouped by raw token so ``identity_from_smiles``
       runs once per distinct token (via ``asyncio.to_thread``, all gathered in parallel);
       invalid tokens fail per original line immediately; results then dedup by ``canonical_key``
       (two SMILES that map to the same InChIKey collapse to one work item; InChIKey inputs share
       the same key-space);
    1. DB-first (serial): ``get_by_key`` for each distinct canonical_key;
    2. enrich (parallel): ``pubchem.fetch_by_inchikey`` fan-out over DB misses via
       ``asyncio.gather``;
    3. persist (serial): upsert each miss; ``manual_source_id()`` only on the structure-only
       path (one call site — do not add a second);
    4. emit: ``resolved`` (distinct, keyed on canonical_key) + ``failed`` (per original line for
       invalids; one entry per unresolvable distinct identity). No silent drops.
    """
    logger.info("validating %d compound input(s)", len(inputs))
    resolved: dict[str, ResolvedCompound] = {}
    failed: list[FailedInput] = []

    # Phase 0a: classify inputs into SMILES groups (raw token -> [(line, value), ...]) and
    # InChIKey inputs. Grouping SMILES by raw token avoids redundant identity_from_smiles calls.
    smiles_groups: dict[str, list[tuple[int, str]]] = {}
    inchikey_lines: list[tuple[int, CompoundInput]] = []

    for idx, item in enumerate(inputs, start=1):
        token = item.value.strip()
        if not token:
            continue
        is_key = item.type == "inchikey" or (item.type is None and structure.is_inchikey(token))
        if is_key:
            inchikey_lines.append((idx, item))
        else:
            if token not in smiles_groups:
                smiles_groups[token] = []
            smiles_groups[token].append((idx, item.value))

    # Phase 0b: compute identity once per distinct SMILES raw token (non-blocking, in parallel).
    distinct_smiles = list(smiles_groups.keys())
    smiles_idents = (
        await asyncio.gather(
            *(asyncio.to_thread(structure.identity_from_smiles, s) for s in distinct_smiles)
        )
        if distinct_smiles
        else []
    )

    # Phase 0c: build work dict from SMILES identity results; invalid tokens fail per original
    # line (preserving the per-line failure count even when the same bad SMILES is repeated).
    work: dict[str, _CompoundWork] = {}
    for raw, ident in zip(distinct_smiles, smiles_idents, strict=True):
        occurrences = smiles_groups[raw]
        if ident is None:
            for line, value in occurrences:
                logger.info("  rejected %r: invalid structure", value)
                failed.append(FailedInput(value=value, reason="invalid structure", line=line))
            continue
        key = canonical.compound_canonical_key({"inchi_key": ident.inchikey})
        if key not in work:
            first_line, first_value = occurrences[0]
            work[key] = _CompoundWork(
                value=first_value,
                line=first_line,
                inchikey=ident.inchikey,
                smiles=ident.canonical_smiles,
            )

    # Phase 0d: InChIKey inputs — validate format per line; add to the shared work dict (dedup).
    for idx, item in inchikey_lines:
        token = item.value.strip()
        if not structure.is_inchikey(token):
            logger.info("  rejected %r: invalid InChIKey format", item.value)
            failed.append(FailedInput(value=item.value, reason="invalid InChIKey format", line=idx))
            continue
        inchikey = token.upper()
        key = canonical.compound_canonical_key({"inchi_key": inchikey})
        if key not in work:
            work[key] = _CompoundWork(value=item.value, line=idx, inchikey=inchikey, smiles=None)

    # Phase 1: DB-first (serial on the single session).
    db_hits: dict[str, Any] = {}
    misses: list[str] = []
    for key in work:
        existing = await repo.get_by_key(key)
        if existing is not None:
            logger.info("  reuse (db hit): %s", existing.canonical_name or existing.canonical_key)
            db_hits[key] = existing
        else:
            misses.append(key)

    # Phase 2: enrich (parallel) — PubChem fan-out over DB misses only.
    miss_works = [work[k] for k in misses]
    pubchem_results: list[Any] = (
        await asyncio.gather(*(pubchem.fetch_by_inchikey(w.inchikey) for w in miss_works))
        if miss_works
        else []
    )

    # Phase 3: persist (serial on the single session). manual_source_id() is called only on the
    # structure-only path (single call site; do not call it elsewhere).
    for key, w, rec in zip(misses, miss_works, pubchem_results, strict=True):
        cid = uuid.UUID(canonical.compound_id_from_key(key))
        if rec is not None:
            logger.info("  enriched via PubChem: %s (CID %s)", rec.name, rec.pubchem_cid)
            row: dict[str, Any] = {
                "compound_id": cid,
                "canonical_key": key,
                "canonical_name": rec.name,
                "inchi_key": w.inchikey,
                "smiles": rec.smiles or w.smiles,
                "pubchem_cid": rec.pubchem_cid,
                "molecular_formula": rec.molecular_formula,
                "molecular_weight": rec.molecular_weight,
                "validation_status": "externally_validated",
                "source_url": (
                    f"https://pubchem.ncbi.nlm.nih.gov/compound/{rec.pubchem_cid}"
                    if rec.pubchem_cid
                    else None
                ),
                "retrieved_at": now_utc(),
            }
            status = "externally_validated"
        elif w.smiles is not None:  # structure-only: SMILES input with no PubChem record
            logger.info("  persisted structure-only: %s", w.inchikey)
            row = {
                "compound_id": cid,
                "canonical_key": key,
                "canonical_name": w.inchikey,
                "inchi_key": w.inchikey,
                "smiles": w.smiles,
                "validation_status": "structure_only",
                "source_id": await repo.manual_source_id(),
                "retrieved_at": now_utc(),
            }
            status = "structure_only"
        else:  # bare InChIKey, not in DB and not in PubChem -> dead end
            logger.info("  rejected %s: not found in the database or PubChem", w.inchikey)
            failed.append(
                FailedInput(
                    value=w.value,
                    reason="not found in the database or PubChem. "
                    "If it is a real compound, paste its SMILES (structure) instead.",
                    line=w.line,
                )
            )
            continue
        await repo.upsert(row)
        resolved[key] = ResolvedCompound(
            compound_id=cid,
            canonical_key=key,
            canonical_name=row["canonical_name"],
            pubchem_cid=row.get("pubchem_cid"),
            validation_status=status,
        )

    # Phase 4: emit DB hits (merged into resolved; canonical_key dedup ensures no duplicates).
    for key, existing in db_hits.items():
        resolved[key] = ResolvedCompound(
            compound_id=existing.compound_id,
            canonical_key=existing.canonical_key,
            canonical_name=existing.canonical_name,
            pubchem_cid=getattr(existing, "pubchem_cid", None),
            validation_status=existing.validation_status,
        )

    logger.info("resolution complete: %d resolved, %d failed", len(resolved), len(failed))
    return list(resolved.values()), failed


async def _lookup_accession(accession: str, repo: Any) -> Any:
    """DB-first lookup of a stored target by one accession's canonical key (serial; no network).

    Returns the stored target row, or ``None`` on a miss. Kept as the single DB-read step so the
    phased ``resolve_targets`` batch and the serial ``resolve_target_accession`` share one home.
    """
    return await repo.get_by_key(canonical.target_canonical_key(uniprot=accession))


async def _fetch_accession(accession: str, uniprot: Any) -> UniProtResolution:
    """Pure-network resolve of one accession to its human (9606) record (parallel-safe).

    Holds no DB session, so many of these can run concurrently under ``asyncio.gather`` (already
    bounded by the UniProt client's ``_SEM(10)``). This is the only liftable, parallel step.
    """
    result: UniProtResolution = await uniprot.resolve(accession)
    return result


async def _persist_accession(
    rec: UniProtRecord, repo: Any, source_id: uuid.UUID | None
) -> ResolvedTarget:
    """Upsert a fetched record canonicalized on its **primary** accession (serial; one upsert)."""
    primary = rec.uniprot_accession
    key = canonical.target_canonical_key(uniprot=primary)
    tid = uuid.UUID(canonical.target_id_from_key(key))
    await repo.upsert(
        {
            "target_id": tid,
            "canonical_key": key,
            "gene_symbol": rec.gene_symbol,
            "protein_name": rec.protein_name,
            "uniprot_accession": primary,
            "source_id": source_id,
            "source_url": f"https://www.uniprot.org/uniprotkb/{primary}/entry",
            "retrieved_at": now_utc(),
        }
    )
    return ResolvedTarget(
        target_id=tid,
        canonical_key=key,
        gene_symbol=rec.gene_symbol,
        uniprot_accession=primary,
        validation_status="externally_validated",
    )


async def resolve_target_accession(
    accession: str,
    repo: Any,
    uniprot: Any,
    *,
    uniprot_source_id: uuid.UUID | None = None,
) -> AccessionResolution:
    """Resolve a single UniProt accession (primary OR secondary) to a human (9606) target.

    DB-first, persisting on a fresh hit. Returns ``AccessionResolution(target=None, reason=...)``
    when the accession is not a resolvable human target (skip — human-only); the ``reason``
    distinguishes a non-UniProt id (``INVALID_ID``) from a genuine no-human miss
    (``NO_HUMAN_RECORD``). Identity is canonicalized on the entry's **primary** accession
    (``rec.uniprot_accession``), so every alias/secondary accession of one protein converges to
    one ``target_id`` — which prevents duplicate target rows for the same protein reached via
    different accessions.

    This is the single home for accession→target resolution: both manual/STP resolution
    (``resolve_targets``) and Stage 3 (``stage3.run``) call it instead of duplicating the
    resolve+canonicalize+persist logic. It composes the three serial/network steps
    (``_lookup_accession`` -> ``_fetch_accession`` -> ``_persist_accession``); ``resolve_targets``
    reuses the same steps batched, but the external behavior here is unchanged.
    """
    acc = accession.strip().upper()

    # Non-UniProt-grammar id (e.g. a PubChem BioAssay RefSeq NP_*/YP_*/XP_*, PDB 1VRU_A, or
    # GenBank AAK85233 accession): it can neither key a stored target (identity canonicalizes on a
    # UniProt primary accession) nor resolve via uniprot.resolve (which searches only
    # accession:/sec_acc: and would 400). Short-circuit without a DB or network round-trip — this
    # removes the dominant Stage-3 runtime cost (thousands of doomed UniProt calls). Reuses the
    # same strict UniProtKB grammar used to classify manual targets. Secondary accessions share
    # the grammar, so they still flow through.
    if not _ACCESSION_RE.match(acc):
        return AccessionResolution(None, UniProtReason.INVALID_ID)

    # Fast path: a target already stored under this exact accession's key — no network call.
    existing = await _lookup_accession(acc, repo)
    if existing is not None:
        return AccessionResolution(_db_hit(existing), None)

    rec_res = await _fetch_accession(acc, uniprot)
    if rec_res.record is None:
        return AccessionResolution(None, rec_res.reason)  # non-human / non-UniProt -> skip

    # Canonicalize on the PRIMARY accession so aliases of one entry converge to one id.
    rec = rec_res.record
    existing = await _lookup_accession(rec.uniprot_accession, repo)
    if existing is not None:
        return AccessionResolution(_db_hit(existing), None)

    source_id = (
        uniprot_source_id
        if uniprot_source_id is not None
        else await repo.source_id_by_name("UniProt")
    )
    return AccessionResolution(await _persist_accession(rec, repo, source_id), None)


def _db_hit(existing: Any) -> ResolvedTarget:
    return ResolvedTarget(
        target_id=existing.target_id,
        canonical_key=existing.canonical_key,
        gene_symbol=existing.gene_symbol,
        uniprot_accession=existing.uniprot_accession,
        validation_status="db_hit",
    )


def _symbol_fail_reason(value: str) -> str:
    """Honest reason for a gene-symbol miss.

    Distinguish a recognized HGNC gene that simply has no protein in UniProt (a non-coding RNA
    gene — microRNA / lncRNA / snoRNA — which has no protein target) from a genuinely unrecognized
    identifier. Uses the offline HGNC status already available via ``gene_symbols.normalize``.
    """
    if gene_symbols.normalize(value).status != "unrecognized":
        return (
            "a recognized human gene with no protein in UniProt "
            "(likely a non-coding RNA gene, which has no protein target)"
        )
    return "not a recognized human (9606) gene symbol or UniProt accession"


@dataclass
class _TargetWork:
    """One distinct, format-valid identity to resolve (a UniProt accession or a gene symbol)."""

    value: str  # original input value (for FailedInput.value)
    line: int  # 1-based line of its FIRST occurrence (for failure reporting)
    kind: str  # "accession" | "symbol"
    from_grammar: bool = False  # accession kind GUESSED from a typeless token (may be a symbol)


async def resolve_targets(
    inputs: Sequence[TargetInput | dict[str, Any]],
    repo: Any,
    uniprot: Any,
    *,
    gene_to_acc: dict[str, str] | None = None,
) -> tuple[list[ResolvedTarget], list[FailedInput]]:
    """Resolve manual targets: classify -> dedup -> DB-first -> UniProt 9606 -> persist.

    Phased so identical inputs resolve once and only the pure-network calls run concurrently —
    a single ``AsyncSession`` cannot run concurrent statements, so all DB reads/writes stay serial
    and only ``resolve_symbol`` / ``_fetch_accession`` fan out via ``asyncio.gather`` (bounded by
    the UniProt client's ``_SEM(10)``):

    0. classify + dedup by normalized identity (accession ``.upper()`` or
       ``gene_symbols.normalize(...).canonical``); invalid-format / InChIKey inputs fail
       immediately per line, the rest collapse to a distinct work-list (first line wins);
    1. symbols -> accessions: DB-first (``get_by_gene_symbol``, serial), misses fan out to
       ``resolve_symbol``;
    2. accessions (direct ∪ symbol-derived): ``_lookup_accession`` (serial), misses fan out to
       ``_fetch_accession``;
    3. persist (serial), canonicalized on the primary accession, dedup-by-primary so aliases
       collapse to one ``target_id`` with no second upsert;
    4. emit one resolved target per distinct identity and one failure per unresolved identity.

    ``gene_to_acc`` is an optional symbol->accession cache/seam. ``line`` (1-based, first
    occurrence) is recorded on failures. No silent drops.
    """
    logger.info("validating %d target input(s)", len(inputs))
    resolved: dict[str, ResolvedTarget] = {}
    failed: list[FailedInput] = []
    gene_to_acc = gene_to_acc or {}
    uniprot_source_id = await repo.source_id_by_name("UniProt")

    # Phase 0: classify + dedup. Invalid-format / InChIKey inputs fail immediately per line; the
    # rest collapse to a distinct work-list keyed on normalized identity (first line wins).
    work: dict[str, _TargetWork] = {}
    for idx, raw in enumerate(inputs, start=1):
        item = raw if isinstance(raw, TargetInput) else TargetInput(**raw)
        token = item.value.strip()
        if not token:
            continue
        is_accession = item.type == "uniprot" or (
            item.type is None and _is_accession_shaped(token.upper())
        )
        if is_accession:
            acc = _accession_base(token.upper())  # P00533-2 (isoform) -> P00533
            if not _ACCESSION_RE.match(acc):
                failed.append(
                    FailedInput(
                        value=item.value, reason="invalid UniProt accession format", line=idx
                    )
                )
                continue
            work.setdefault(
                acc,
                _TargetWork(
                    value=item.value, line=idx, kind="accession", from_grammar=item.type is None
                ),
            )
        else:
            if structure.is_inchikey(token):
                # A compound InChIKey pasted into a target box is neither a gene symbol nor a
                # UniProt accession; report it as such rather than as a non-human (9606) miss.
                failed.append(
                    FailedInput(
                        value=item.value,
                        reason="looks like a compound InChIKey, not a gene symbol or "
                        "UniProt accession",
                        line=idx,
                    )
                )
                continue
            sym = gene_symbols.normalize(token).canonical
            work.setdefault(sym, _TargetWork(value=item.value, line=idx, kind="symbol"))

    # Phase 1: distinct symbols -> accessions. DB-first (serial); UniProt misses fan out.
    sym_acc: dict[str, str] = {}
    sym_misses: list[str] = []
    for sym, wi in work.items():
        if wi.kind != "symbol":
            continue
        acc = gene_to_acc.get(sym, "")
        if not acc:
            cached = await repo.get_by_gene_symbol(sym)  # DB-first: skip UniProt if known
            if cached is not None and cached.uniprot_accession:
                acc = cached.uniprot_accession
                gene_to_acc[sym] = acc
        if acc:
            sym_acc[sym] = acc
        else:
            sym_misses.append(sym)
    if sym_misses and hasattr(uniprot, "resolve_symbol"):
        sym_results = await asyncio.gather(*(uniprot.resolve_symbol(s) for s in sym_misses))
        for sym, res in zip(sym_misses, sym_results, strict=True):
            if res.record is not None and res.record.uniprot_accession:
                sym_acc[sym] = res.record.uniprot_accession

    # Phase 2: distinct accessions (direct ∪ symbol-derived). DB-first (serial); misses fan out.
    acc_order: list[str] = []
    acc_seen: set[str] = set()
    for key, wi in work.items():
        acc = key if wi.kind == "accession" else sym_acc.get(key, "")
        if acc and acc not in acc_seen:
            acc_seen.add(acc)
            acc_order.append(acc)

    acc_target: dict[str, ResolvedTarget] = {}
    persisted: dict[str, ResolvedTarget] = {}  # primary canonical_key -> target (dedup-by-primary)
    acc_misses: list[str] = []
    for acc in acc_order:
        existing = await _lookup_accession(acc, repo)
        if existing is not None:
            target = _db_hit(existing)
            persisted[target.canonical_key] = target  # DB hit short-circuits into persisted
            acc_target[acc] = target
        else:
            acc_misses.append(acc)
    fetched = (
        await asyncio.gather(*(_fetch_accession(acc, uniprot) for acc in acc_misses))
        if acc_misses
        else []
    )

    # Phase 3: persist (serial), canonicalized on the primary accession. Skip a primary already
    # persisted this batch so aliases collapse to one target_id with no second upsert.
    acc_fail: dict[str, UniProtReason | None] = {}
    for acc, res in zip(acc_misses, fetched, strict=True):
        if res.record is None:
            acc_fail[acc] = res.reason
            continue
        rec = res.record
        primary_key = canonical.target_canonical_key(uniprot=rec.uniprot_accession)
        if primary_key in persisted:
            acc_target[acc] = persisted[primary_key]
            continue
        existing = await _lookup_accession(rec.uniprot_accession, repo)
        if existing is not None:
            target = _db_hit(existing)
        else:
            target = await _persist_accession(rec, repo, uniprot_source_id)
        persisted[primary_key] = target
        acc_target[acc] = target

    # Phase 3.5: symbol fallback for grammar-guessed accessions. A TYPELESS token shaped like a
    # UniProt accession but absent from UniProt may actually be a gene symbol that collides with
    # the accession grammar (e.g. P2RY12 is both a real gene symbol AND accession-shaped: P + digit
    # + 3 alnum + digit). Retry those (and only those) as gene symbols before failing. An EXPLICIT
    # type=uniprot input is never retried (the user asserted it is an accession).
    fallback = [
        (acc, work[acc]) for acc in acc_misses if acc in acc_fail and work[acc].from_grammar
    ]
    if fallback and hasattr(uniprot, "resolve_symbol"):
        fb_syms = [gene_symbols.normalize(wi.value.strip()).canonical for _, wi in fallback]
        fb_res = await asyncio.gather(*(uniprot.resolve_symbol(s) for s in fb_syms))
        for (acc, _wi), res in zip(fallback, fb_res, strict=True):
            rec = res.record
            if rec is None or not rec.uniprot_accession:
                continue  # genuinely neither a human accession nor a gene symbol -> stays failed
            primary_key = canonical.target_canonical_key(uniprot=rec.uniprot_accession)
            if primary_key in persisted:
                target = persisted[primary_key]
            else:
                existing = await _lookup_accession(rec.uniprot_accession, repo)
                target = (
                    _db_hit(existing)
                    if existing is not None
                    else await _persist_accession(rec, repo, uniprot_source_id)
                )
                persisted[primary_key] = target
            acc_target[acc] = target
            acc_fail.pop(acc, None)  # resolved via fallback; clear the accession failure

    # Phase 4: emit one resolved target per distinct identity (deduped on canonical_key) and one
    # failure per unresolved identity, carrying its first source line. No silent drops.
    for key, wi in work.items():
        if wi.kind == "symbol":
            acc = sym_acc.get(key, "")
            if not acc:
                failed.append(
                    FailedInput(value=wi.value, reason=_symbol_fail_reason(wi.value), line=wi.line)
                )
                continue
        else:
            acc = key
        hit = acc_target.get(acc)
        if hit is None:
            if wi.from_grammar:
                # We tried BOTH an accession lookup and a gene-symbol fallback: it is neither.
                reason = _symbol_fail_reason(wi.value)
            else:
                reason_enum = acc_fail.get(acc)
                reason = (
                    _ACCESSION_FAIL_MSG.get(reason_enum, "not a human (9606) UniProt accession")
                    if reason_enum is not None
                    else "not a human (9606) UniProt accession"
                )
            failed.append(FailedInput(value=wi.value, reason=reason, line=wi.line))
            continue
        resolved[hit.canonical_key] = hit  # dedup on primary key

    logger.info("target resolution complete: %d resolved, %d failed", len(resolved), len(failed))
    return list(resolved.values()), failed
