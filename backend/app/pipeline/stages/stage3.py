"""Stage 3 — measured compound→target identification (ChEMBL + PubChem BioAssay).

Per compound, the union of measured targets from two sources is built, deduped per
(compound, target) pair with a fixed precedence, resolved to human (9606) UniProt
records, and persisted as targets + measured edges.

Precedence (per pair): **ChEMBL beats PubChem** (measured-curated > screened). The
``winner`` map is built by inserting PubChem accessions first then ChEMBL hits, so
ChEMBL overwrites a shared accession.

Human-only (ledger rule): ChEMBL accessions are already human; PubChem accessions are
NOT organism-filtered. The resolver returns ``None`` for any accession that does not map
to a human UniProt record (existing DB target or a fresh ``uniprot.resolve`` hit), and
``compute`` skips it — no target, no edge, not counted in coverage.

Coverage is reported, never gated: a compound with zero resolved targets is surfaced in
``per_compound`` with ``coverage: 0``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import now_utc
from app.integrations.chembl import ChemblClient
from app.integrations.pubchem_bioassay import PubChemBioAssayClient
from app.integrations.uniprot import UniProtClient
from app.repositories.compound import CompoundRepository
from app.repositories.compound_target import CompoundTargetRepository
from app.repositories.target import TargetRepository
from app.services import canonical
from app.services.input_validation import resolve_target_accession

logger = logging.getLogger("herbaflow.pipeline")

# Resolve a UniProt accession to (target_id, gene_symbol, canonical_key), or None when
# the accession is not a human (9606) target and must be skipped (human-only).
TargetResolver = Callable[[str], Awaitable[tuple[uuid.UUID, str | None, str] | None]]


async def compute(
    compounds: list[dict[str, Any]],
    chembl: Any,
    pubchem: Any,
    *,
    resolve_target: TargetResolver,
    min_pchembl: float,
    min_confidence: int,
) -> dict[str, Any]:
    """Pure-ish core: union + dedupe + precedence + human-only resolve + coverage.

    ``resolve_target`` returning ``None`` means "not a human target" — the accession is
    skipped (no edge, not counted). Coverage is reported per compound, never gated.
    """
    targets: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    per_compound: dict[str, dict[str, int]] = {}

    async def _one(c: dict[str, Any]) -> None:
        ik = c.get("inchi_key")
        cid = str(c["compound_id"])
        if not ik:
            per_compound[cid] = {"coverage": 0}
            return
        chembl_hits = await chembl.targets_for_inchikey(
            ik, min_pchembl=min_pchembl, min_confidence=min_confidence
        )
        pubchem_accs = await pubchem.active_targets_for_inchikey(ik)

        # PubChem first, then ChEMBL overwrites the shared pair -> ChEMBL wins.
        winner: dict[str, tuple[str, float | None]] = {}
        for acc in pubchem_accs:
            winner[acc] = ("pubchem_bioassay", None)
        for h in chembl_hits:
            winner[h.uniprot_accession] = ("chembl_bioactivity", h.pchembl_value)

        coverage = 0
        for acc, (method, pchembl) in winner.items():
            resolved = await resolve_target(acc)
            if resolved is None:
                continue  # not a human UniProt target -> skip (human-only)
            tid, gene, _key = resolved
            tid_s = str(tid)
            targets.setdefault(tid_s, {"target_id": tid_s, "canonical_name": gene or acc})
            edges.append(
                {
                    "compound_id": cid,
                    "target_id": tid_s,
                    "prediction_method": method,
                    "pchembl_value": pchembl,
                    "score": pchembl,
                    "source_url": f"https://www.uniprot.org/uniprotkb/{acc}/entry",
                    "uniprot_accession": acc,
                }
            )
            coverage += 1
        per_compound[cid] = {"coverage": coverage}

    await asyncio.gather(*(_one(c) for c in compounds))

    covered = sum(1 for v in per_compound.values() if v["coverage"] > 0)
    coverage_pct = round(100.0 * covered / len(compounds), 1) if compounds else 0.0
    return {
        "targets": list(targets.values()),
        "compound_targets": edges,
        "per_compound": per_compound,
        "coverage_pct": coverage_pct,
        "count": len(targets),
        "state": "computed",
    }


async def run(
    session: AsyncSession,
    step2_passed: list[dict[str, Any]],
    params: dict[str, Any],
    *,
    chembl: Any = None,
    pubchem: Any = None,
    uniprot: Any = None,
) -> dict[str, Any]:
    """Fetch structures, build a DB-first + human-only resolver, compute, persist.

    External clients are dependency-injectable so tests can pass fakes; when omitted a
    shared ``httpx.AsyncClient`` backs the real clients.
    """
    ids = [uuid.UUID(c["compound_id"]) for c in step2_passed]
    comp_repo = CompoundRepository(session)
    target_repo = TargetRepository(session)
    edge_repo = CompoundTargetRepository(session)
    rows = await comp_repo.get_many(ids)
    compounds = [
        {
            "compound_id": str(r.compound_id),
            "inchi_key": r.inchi_key,
            "canonical_name": r.canonical_name,
        }
        for r in rows
    ]
    chembl_src = await target_repo.source_id_by_name("ChEMBL")
    pubchem_src = await target_repo.source_id_by_name("PubChem BioAssay")
    uniprot_src = await target_repo.source_id_by_name("UniProt")

    async def _go(chembl_c: Any, pubchem_c: Any, uniprot_c: Any) -> dict[str, Any]:
        async def _resolve(accession: str) -> tuple[uuid.UUID, str | None, str] | None:
            # Shared canonical resolver: identity is keyed on the UniProt primary accession,
            # so a measured accession and a manually-added alias of the same protein map to
            # one target_id (no duplicate rows). See input_validation.resolve_target_accession.
            rt = await resolve_target_accession(
                accession, target_repo, uniprot_c, uniprot_source_id=uniprot_src
            )
            if rt is None:
                return None  # non-human / unresolvable -> skip
            return rt.target_id, rt.gene_symbol, rt.canonical_key

        return await compute(
            compounds,
            chembl_c,
            pubchem_c,
            resolve_target=_resolve,
            min_pchembl=float(params["min_pchembl"]),
            min_confidence=int(params["min_assay_confidence"]),
        )

    if chembl is not None and pubchem is not None and uniprot is not None:
        result = await _go(chembl, pubchem, uniprot)
    else:
        async with httpx.AsyncClient() as client:
            result = await _go(
                chembl or ChemblClient(client),
                pubchem or PubChemBioAssayClient(client),
                uniprot or UniProtClient(client),
            )

    src_by_method = {"chembl_bioactivity": chembl_src, "pubchem_bioassay": pubchem_src}
    for e in result["compound_targets"]:
        cid = uuid.UUID(e["compound_id"])
        tid = uuid.UUID(e["target_id"])
        await edge_repo.upsert_measured(
            {
                "compound_target_id": uuid.UUID(canonical.compound_target_id(str(cid), str(tid))),
                "compound_id": cid,
                "target_id": tid,
                "prediction_method": e["prediction_method"],
                "score": e.get("score"),
                "pchembl_value": e.get("pchembl_value"),
                "source_id": src_by_method.get(e["prediction_method"]),
                "source_url": e.get("source_url"),
                "retrieved_at": now_utc(),
            }
        )
    logger.info(
        "stage 3: %d target(s) across %d compound(s), coverage %.1f%%",
        result["count"],
        len(compounds),
        result["coverage_pct"],
    )
    return result
