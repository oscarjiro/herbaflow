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
from app.integrations.uniprot import UniProtReason, UniProtResolution
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

# Honest accession-failure wording, distinguishing the two causes the UniProt client already
# separates: a 400 (not a resolvable UniProt query at all) vs a valid query with no human hit.
_ACCESSION_FAIL_MSG = {
    UniProtReason.INVALID_ID: "not a UniProt accession",
    UniProtReason.NO_HUMAN_RECORD: "no human (9606) UniProt record",
}


async def resolve_compounds(
    inputs: list[CompoundInput], repo: Any, pubchem: Any
) -> tuple[list[ResolvedCompound], list[FailedInput]]:
    logger.info("validating %d compound input(s)", len(inputs))
    resolved: dict[str, ResolvedCompound] = {}
    failed: list[FailedInput] = []

    for idx, item in enumerate(inputs, start=1):
        token = item.value.strip()
        if not token:
            continue
        is_key = item.type == "inchikey" or (item.type is None and structure.is_inchikey(token))

        # 1. Identity
        if is_key:
            if not structure.is_inchikey(token):
                logger.info("  rejected %r: invalid InChIKey format", item.value)
                failed.append(
                    FailedInput(value=item.value, reason="invalid InChIKey format", line=idx)
                )
                continue
            inchikey, smiles = token.upper(), None
        else:
            ident = await asyncio.to_thread(structure.identity_from_smiles, token)
            if ident is None:
                logger.info("  rejected %r: invalid structure", item.value)
                failed.append(FailedInput(value=item.value, reason="invalid structure", line=idx))
                continue
            inchikey, smiles = ident.inchikey, ident.canonical_smiles

        canonical_key = canonical.compound_canonical_key({"inchi_key": inchikey})
        cid = uuid.UUID(canonical.compound_id_from_key(canonical_key))
        if canonical_key in resolved:  # input-level dedupe
            continue

        # 2. DB-first
        existing = await repo.get_by_key(canonical_key)
        if existing is not None:
            logger.info("  reuse (db hit): %s", existing.canonical_name or existing.canonical_key)
            resolved[canonical_key] = ResolvedCompound(
                compound_id=existing.compound_id,
                canonical_key=existing.canonical_key,
                canonical_name=existing.canonical_name,
                validation_status=existing.validation_status,
            )
            continue

        # 3. Enrich from PubChem
        rec = await pubchem.fetch_by_inchikey(inchikey)
        if rec is not None:
            logger.info("  enriched via PubChem: %s (CID %s)", rec.name, rec.pubchem_cid)
            row: dict[str, Any] = {
                "compound_id": cid,
                "canonical_key": canonical_key,
                "canonical_name": rec.name,
                "inchi_key": inchikey,
                "smiles": rec.smiles or smiles,
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
        elif smiles is not None:  # structure-only (SMILES with no PubChem row)
            logger.info("  persisted structure-only: %s", inchikey)
            row = {
                "compound_id": cid,
                "canonical_key": canonical_key,
                "canonical_name": inchikey,
                "inchi_key": inchikey,
                "smiles": smiles,
                "validation_status": "structure_only",
                "source_id": await repo.manual_source_id(),
                "retrieved_at": now_utc(),
            }
            status = "structure_only"
        else:  # bare InChIKey, nowhere found -> dead end
            logger.info("  rejected %s: not found in the database or PubChem", inchikey)
            failed.append(
                FailedInput(
                    value=item.value,
                    reason="not found in the database or PubChem. "
                    "If it is a real compound, paste its SMILES (structure) instead.",
                    line=idx,
                )
            )
            continue

        await repo.upsert(row)
        resolved[canonical_key] = ResolvedCompound(
            compound_id=cid,
            canonical_key=canonical_key,
            canonical_name=row["canonical_name"],
            validation_status=status,
        )

    logger.info("resolution complete: %d resolved, %d failed", len(resolved), len(failed))
    return list(resolved.values()), failed


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
    resolve+canonicalize+persist logic.
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
    input_key = canonical.target_canonical_key(uniprot=acc)
    existing = await repo.get_by_key(input_key)
    if existing is not None:
        return AccessionResolution(_db_hit(existing), None)

    rec_res: UniProtResolution = await uniprot.resolve(acc)
    if rec_res.record is None:
        return AccessionResolution(None, rec_res.reason)  # non-human / non-UniProt -> skip

    # Canonicalize on the PRIMARY accession so aliases of one entry converge to one id.
    rec = rec_res.record
    primary = rec.uniprot_accession
    key = canonical.target_canonical_key(uniprot=primary)
    tid = uuid.UUID(canonical.target_id_from_key(key))

    existing = await repo.get_by_key(key)
    if existing is not None:
        return AccessionResolution(_db_hit(existing), None)

    source_id = (
        uniprot_source_id
        if uniprot_source_id is not None
        else await repo.source_id_by_name("UniProt")
    )
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
    return AccessionResolution(
        ResolvedTarget(
            target_id=tid,
            canonical_key=key,
            gene_symbol=rec.gene_symbol,
            uniprot_accession=primary,
            validation_status="externally_validated",
        ),
        None,
    )


def _db_hit(existing: Any) -> ResolvedTarget:
    return ResolvedTarget(
        target_id=existing.target_id,
        canonical_key=existing.canonical_key,
        gene_symbol=existing.gene_symbol,
        uniprot_accession=existing.uniprot_accession,
        validation_status="db_hit",
    )


async def resolve_targets(
    inputs: Sequence[TargetInput | dict[str, Any]],
    repo: Any,
    uniprot: Any,
    *,
    gene_to_acc: dict[str, str] | None = None,
) -> tuple[list[ResolvedTarget], list[FailedInput]]:
    """Resolve manual targets: classify -> HGNC -> dedupe -> DB-first -> UniProt 9606 -> persist.

    ``gene_to_acc`` is an optional symbol->accession map (test seam / cache); when a symbol
    is not present, the UniProt client resolves it via resolve_symbol. ``line`` (1-based)
    is recorded on failures.
    """
    logger.info("validating %d target input(s)", len(inputs))
    resolved: dict[str, ResolvedTarget] = {}
    failed: list[FailedInput] = []
    gene_to_acc = gene_to_acc or {}
    uniprot_source_id = await repo.source_id_by_name("UniProt")

    for idx, raw in enumerate(inputs, start=1):
        item = raw if isinstance(raw, TargetInput) else TargetInput(**raw)
        token = item.value.strip()
        if not token:
            continue

        is_accession = item.type == "uniprot" or (
            item.type is None and _ACCESSION_RE.match(token.upper()) is not None
        )

        if is_accession:
            acc = token.upper()
            if not _ACCESSION_RE.match(acc):
                failed.append(
                    FailedInput(
                        value=item.value, reason="invalid UniProt accession format", line=idx
                    )
                )
                continue
        else:
            sym = gene_symbols.normalize(token).canonical
            acc = gene_to_acc.get(sym, "")
            if not acc:
                cached = await repo.get_by_gene_symbol(sym)  # DB-first: skip UniProt if known
                if cached is not None and cached.uniprot_accession:
                    acc = cached.uniprot_accession
                    gene_to_acc[sym] = acc
            if not acc:
                sym_res = (
                    await uniprot.resolve_symbol(sym)
                    if hasattr(uniprot, "resolve_symbol")
                    else UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)
                )
                acc = sym_res.record.uniprot_accession if sym_res.record else ""
            if not acc:
                failed.append(
                    FailedInput(
                        value=item.value,
                        reason="gene symbol not found in human (9606) UniProt",
                        line=idx,
                    )
                )
                continue

        acc_res = await resolve_target_accession(
            acc, repo, uniprot, uniprot_source_id=uniprot_source_id
        )
        if acc_res.target is None:
            reason = (
                _ACCESSION_FAIL_MSG.get(acc_res.reason, "not a human (9606) UniProt accession")
                if acc_res.reason is not None
                else "not a human (9606) UniProt accession"
            )
            failed.append(FailedInput(value=item.value, reason=reason, line=idx))
            continue
        resolved[acc_res.target.canonical_key] = acc_res.target  # dedup on primary key

    logger.info("target resolution complete: %d resolved, %d failed", len(resolved), len(failed))
    return list(resolved.values()), failed
