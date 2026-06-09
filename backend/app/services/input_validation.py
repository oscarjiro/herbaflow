"""Manual-input resolution: classify -> identity -> DB-first -> enrich -> persist."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import Sequence
from typing import Any

from app.clock import now_utc
from app.schemas.compound import CompoundInput, FailedInput, ResolvedCompound
from app.schemas.target import ResolvedTarget, TargetInput
from app.services import canonical, gene_symbols, structure

logger = logging.getLogger("herbaflow.resolution")

_ACCESSION_RE = re.compile(r"^[A-Z0-9]{6,10}$")


async def resolve_compounds(
    inputs: list[CompoundInput], repo: Any, pubchem: Any
) -> tuple[list[ResolvedCompound], list[FailedInput]]:
    logger.info("validating %d compound input(s)", len(inputs))
    resolved: dict[str, ResolvedCompound] = {}
    failed: list[FailedInput] = []

    for item in inputs:
        token = item.value.strip()
        if not token:
            continue
        is_key = item.type == "inchikey" or (item.type is None and structure.is_inchikey(token))

        # 1. Identity
        if is_key:
            if not structure.is_inchikey(token):
                logger.info("  rejected %r: invalid InChIKey format", item.value)
                failed.append(FailedInput(value=item.value, reason="invalid InChIKey format"))
                continue
            inchikey, smiles = token.upper(), None
        else:
            ident = await asyncio.to_thread(structure.identity_from_smiles, token)
            if ident is None:
                logger.info("  rejected %r: invalid structure", item.value)
                failed.append(FailedInput(value=item.value, reason="invalid structure"))
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
                rec0 = (
                    await uniprot.resolve_symbol(sym)
                    if hasattr(uniprot, "resolve_symbol")
                    else None
                )
                acc = rec0.uniprot_accession if rec0 else ""
            if not acc:
                failed.append(
                    FailedInput(
                        value=item.value,
                        reason="gene symbol not resolved to a human UniProt accession",
                        line=idx,
                    )
                )
                continue

        canonical_key = canonical.target_canonical_key(uniprot=acc)
        if canonical_key in resolved:
            continue
        tid = uuid.UUID(canonical.target_id_from_key(canonical_key))

        existing = await repo.get_by_key(canonical_key)
        if existing is not None:
            resolved[canonical_key] = ResolvedTarget(
                target_id=existing.target_id,
                canonical_key=existing.canonical_key,
                gene_symbol=existing.gene_symbol,
                uniprot_accession=existing.uniprot_accession,
                validation_status="db_hit",
            )
            continue

        rec = await uniprot.resolve(acc)
        if rec is None:
            failed.append(
                FailedInput(
                    value=item.value, reason="not a human (9606) UniProt accession", line=idx
                )
            )
            continue

        await repo.upsert(
            {
                "target_id": tid,
                "canonical_key": canonical_key,
                "gene_symbol": rec.gene_symbol,
                "protein_name": rec.protein_name,
                "uniprot_accession": rec.uniprot_accession,
                "source_id": await repo.source_id_by_name("UniProt"),
                "source_url": f"https://www.uniprot.org/uniprotkb/{rec.uniprot_accession}/entry",
                "retrieved_at": now_utc(),
            }
        )
        resolved[canonical_key] = ResolvedTarget(
            target_id=tid,
            canonical_key=canonical_key,
            gene_symbol=rec.gene_symbol,
            uniprot_accession=rec.uniprot_accession,
            validation_status="externally_validated",
        )

    logger.info("target resolution complete: %d resolved, %d failed", len(resolved), len(failed))
    return list(resolved.values()), failed
