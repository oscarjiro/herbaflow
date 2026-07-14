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
from app.pipeline.genes import target_display_name
from app.repositories.compound import CompoundRepository
from app.repositories.compound_target import CompoundTargetRepository
from app.repositories.target import TargetRepository
from app.services.input_validation import resolve_target_accession

logger = logging.getLogger("herbaflow.pipeline")

# Resolve a UniProt accession to (target_id, gene_symbol), or None when the accession is
# not a human (9606) target and must be skipped (human-only).
TargetResolver = Callable[[str], Awaitable[tuple[uuid.UUID, str | None] | None]]


async def compute(
    compounds: list[dict[str, Any]],
    chembl: Any,
    pubchem: Any,
    *,
    resolve_target: TargetResolver,
    min_pchembl: float,
    min_confidence: int,
    reporter: Any = None,
    progress_base: int = 0,
    progress_total: int | None = None,
) -> dict[str, Any]:
    """Pure-ish core: union + dedupe + precedence + human-only resolve + coverage.

    ``resolve_target`` returning ``None`` means "not a human target" — the accession is
    skipped (no edge, not counted). Coverage is reported per compound, never gated.
    """
    targets: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    per_compound: dict[str, dict[str, int]] = {}
    done = 0
    total = progress_total if progress_total is not None else (progress_base + len(compounds))

    async def _one(c: dict[str, Any]) -> None:
        nonlocal done
        ik = c.get("inchi_key")
        cid = str(c["compound_id"])
        if not ik:
            per_compound[cid] = {"coverage": 0}
        else:
            chembl_hits = await chembl.targets_for_inchikey(
                ik,
                min_pchembl=min_pchembl,
                min_confidence=min_confidence,
                connectivity_key=c.get("connectivity_key"),
            )
            pubchem_accs = await pubchem.active_targets_for_inchikey(ik)

            # PubChem first, then ChEMBL overwrites the shared pair -> ChEMBL wins.
            winner: dict[str, tuple[str, float | None]] = {}
            for acc in pubchem_accs:
                winner[acc] = ("pubchem_bioassay", None)
            for h in chembl_hits:
                winner[h.uniprot_accession] = ("chembl_bioactivity", h.pchembl_value)

            # Collapse resolved accessions to ONE edge per distinct target_id, ChEMBL > PubChem.
            # Two different accessions (e.g. a primary + a secondary of one protein) can resolve to
            # the same target_id; counting raw accessions overcounts coverage and emits duplicate
            # in-memory edges (the DB upsert is pair-keyed, so durable data was already correct).
            by_target: dict[str, dict[str, Any]] = {}
            for acc, (method, pchembl) in winner.items():
                resolved = await resolve_target(acc)
                if resolved is None:
                    continue  # not a human UniProt target -> skip (human-only)
                tid, gene = resolved
                tid_s = str(tid)
                targets.setdefault(
                    tid_s,
                    {
                        "target_id": tid_s,
                        "canonical_name": target_display_name(gene, acc),
                        "gene_symbol": gene,
                        "uniprot_accession": acc,
                    },
                )
                cand = {
                    "compound_id": cid,
                    "target_id": tid_s,
                    "prediction_method": method,
                    "pchembl_value": pchembl,
                    "score": pchembl,
                    "source_url": f"https://www.uniprot.org/uniprotkb/{acc}/entry",
                    "uniprot_accession": acc,
                }
                prev = by_target.get(tid_s)
                if prev is None or (
                    method == "chembl_bioactivity"
                    and prev["prediction_method"] != "chembl_bioactivity"
                ):
                    by_target[tid_s] = cand
            edges.extend(by_target.values())
            per_compound[cid] = {"coverage": len(by_target)}

        # Count this compound's completion on EVERY path (incl. the no-InChIKey early case).
        # `done += 1` is synchronous (no await between read and write), so concurrent _one
        # coroutines increment it safely; only the report awaits.
        done += 1
        if reporter is not None:
            await reporter.update(3, progress_base + done, total)

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


def _reuse_edges(
    cached: list[dict[str, Any]], *, min_pchembl: float, min_confidence: int
) -> list[dict[str, Any]] | None:
    """Decide whether a compound's cached edges can serve this run, and re-filter if so.

    Returns the reusable edge list, or ``None`` meaning "refetch". Reuse is sound only when the
    cached set was discovered at the SAME assay confidence (not re-filterable from the edge) and an
    EQUAL-OR-LOOSER pchembl (so re-filtering ``pchembl_value >= min_pchembl`` cannot miss edges that
    were never fetched). PubChem edges (no pchembl) are always kept. Legacy null-param edges ->
    refetch.
    """
    if not cached:
        return None
    for e in cached:
        if e.get("min_assay_confidence") != min_confidence:
            return None
        dp = e.get("min_pchembl")
        if dp is None:
            logger.debug(
                "stage 3 reuse miss: legacy null-param edge, refetching (target=%s)",
                e.get("target_id"),
            )
            return None
        if dp > min_pchembl:
            return None
    kept: list[dict[str, Any]] = []
    for e in cached:
        if e["prediction_method"] == "chembl_bioactivity":
            pv = e.get("pchembl_value")
            if pv is not None and pv < min_pchembl:
                continue
        kept.append(e)
    return kept


async def run(
    session: AsyncSession,
    step2_passed: list[dict[str, Any]],
    params: dict[str, Any],
    *,
    chembl: Any = None,
    pubchem: Any = None,
    uniprot: Any = None,
    reporter: Any = None,
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
            "connectivity_key": r.connectivity_key,
            "canonical_name": r.canonical_name,
        }
        for r in rows
    ]
    min_pchembl = float(params["min_pchembl"])
    min_confidence = int(params["min_assay_confidence"])

    # Reuse persisted edges per compound when the run's discovery params are compatible (D9):
    # confidence must match exactly (not re-derivable from the edge) and the cached pchembl floor
    # must be equal-or-looser (so a tighter run can re-filter from the stored pchembl_value, but a
    # looser run cannot recover edges that were never fetched). Otherwise the compound is refetched.
    reused_targets: dict[str, dict[str, Any]] = {}
    reused_edges: list[dict[str, Any]] = []
    reused_per_compound: dict[str, dict[str, int]] = {}
    to_fetch: list[dict[str, Any]] = []
    for c in compounds:
        cid = str(c["compound_id"])
        cached = await edge_repo.edges_for_compound(uuid.UUID(cid))
        kept = _reuse_edges(cached, min_pchembl=min_pchembl, min_confidence=min_confidence)
        if kept is None:
            to_fetch.append(c)
            continue
        # Build the SAME shapes compute() emits (one shaping path): one edge per distinct
        # target_id with ChEMBL > PubChem precedence, and a target row whose canonical_name is
        # derived gene_symbol -> uniprot_accession -> target_id (matching compute's `gene or acc`).
        by_target: dict[str, dict[str, Any]] = {}
        for e in kept:
            tid = e["target_id"]
            acc = e.get("uniprot_accession")
            gene = e.get("gene_symbol")
            cand = {
                "compound_id": cid,
                "target_id": tid,
                "prediction_method": e["prediction_method"],
                "pchembl_value": e.get("pchembl_value"),
                "score": e.get("score"),
                "source_url": e.get("source_url"),
                "uniprot_accession": acc,
            }
            prev = by_target.get(tid)
            if prev is None or (
                e["prediction_method"] == "chembl_bioactivity"
                and prev["prediction_method"] != "chembl_bioactivity"
            ):
                by_target[tid] = cand
            reused_targets.setdefault(
                tid,
                {
                    "target_id": tid,
                    "canonical_name": target_display_name(gene, acc, tid),
                    "gene_symbol": gene,
                    "uniprot_accession": acc,
                },
            )
        reused_edges.extend(by_target.values())
        reused_per_compound[cid] = {"coverage": len(by_target)}

    # Per-item progress spans ALL compounds: the reused ones are already done at this point, so
    # report them as the baseline; compute() then climbs from this base to total as each fetched
    # compound completes (base + len(to_fetch) == total).
    progress_total = len(compounds)
    progress_base = len(reused_per_compound)
    if reporter is not None:
        await reporter.update(3, progress_base, progress_total)

    logger.info("stage 3: reuse %d compound(s), fetch %d", len(reused_per_compound), len(to_fetch))

    async def _go(chembl_c: Any, pubchem_c: Any, uniprot_c: Any) -> dict[str, Any]:
        async def _resolve(accession: str) -> tuple[uuid.UUID, str | None] | None:
            # Shared canonical resolver: identity is keyed on the UniProt primary accession,
            # so a measured accession and a manually-added alias of the same protein map to
            # one target_id (no duplicate rows). See input_validation.resolve_target_accession.
            acc_res = await resolve_target_accession(accession, target_repo, uniprot_c)
            rt = acc_res.target
            if rt is None:
                return None  # non-human / unresolvable -> skip
            return rt.target_id, rt.gene_symbol

        return await compute(
            to_fetch,
            chembl_c,
            pubchem_c,
            resolve_target=_resolve,
            min_pchembl=min_pchembl,
            min_confidence=min_confidence,
            reporter=reporter,
            progress_base=progress_base,
            progress_total=progress_total,
        )

    if not to_fetch:
        # Nothing to fetch -> never touch the external clients (injected raise-if-called fakes
        # must not be invoked when every compound reused its cached edges).
        result: dict[str, Any] = {
            "targets": [],
            "compound_targets": [],
            "per_compound": {},
            "coverage_pct": 0.0,
            "count": 0,
            "state": "computed",
        }
    elif chembl is not None and pubchem is not None and uniprot is not None:
        result = await _go(chembl, pubchem, uniprot)
    else:
        async with httpx.AsyncClient() as client:
            result = await _go(
                chembl or ChemblClient(client),
                pubchem or PubChemBioAssayClient(client),
                uniprot or UniProtClient(client),
            )

    # Replace (not upsert) each fetched compound's edges: drop its stale set, write the fresh one
    # stamped with the discovery params. Replace-on-fetch keeps exactly one discovery-param pair per
    # compound and removes edges that fell below a now-stricter threshold.
    fresh_by_compound: dict[str, list[dict[str, Any]]] = {
        str(c["compound_id"]): [] for c in to_fetch
    }
    for e in result["compound_targets"]:
        fresh_by_compound[e["compound_id"]].append(
            {
                "target_id": e["target_id"],
                "prediction_method": e["prediction_method"],
                "pchembl_value": e.get("pchembl_value"),
                "score": e.get("score"),
                "source_url": e.get("source_url"),
                "retrieved_at": now_utc(),
                "min_pchembl": min_pchembl,
                "min_assay_confidence": min_confidence,
            }
        )
    for cid, fresh_rows in fresh_by_compound.items():
        await edge_repo.replace_for_compound(uuid.UUID(cid), fresh_rows)

    # Merge reused + freshly-fetched into one result over ALL compounds (single shape).
    merged_targets = {**reused_targets, **{t["target_id"]: t for t in result["targets"]}}
    merged_edges = reused_edges + result["compound_targets"]
    merged_per_compound = {**reused_per_compound, **result["per_compound"]}
    covered = sum(1 for v in merged_per_compound.values() if v["coverage"] > 0)
    coverage_pct = round(100.0 * covered / len(compounds), 1) if compounds else 0.0
    final = {
        "targets": list(merged_targets.values()),
        "compound_targets": merged_edges,
        "per_compound": merged_per_compound,
        "coverage_pct": coverage_pct,
        "count": len(merged_targets),
        "state": "computed",
    }
    logger.info(
        "stage 3: %d target(s) across %d compound(s) (%d reused, %d fetched), coverage %.1f%%",
        final["count"],
        len(compounds),
        len(reused_per_compound),
        len(to_fetch),
        coverage_pct,
    )
    return final
