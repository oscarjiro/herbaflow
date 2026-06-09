"""Manual-input resolution: classify -> identity -> DB-first -> enrich -> persist."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from app.clock import now_utc
from app.schemas.compound import CompoundInput, FailedInput, ResolvedCompound
from app.services import canonical, structure

logger = logging.getLogger("herbaflow.resolution")


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
