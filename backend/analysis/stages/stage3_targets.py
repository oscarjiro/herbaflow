import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)
from app.models.analysis import AnalysisRun
from app.models.target import CompoundTarget, Target
from app.repositories import compound_repo
from app.repositories.analysis_repo import now_utc
from app.services.canonicalize import (
    TARGET_NS,  # noqa: F401 — re-exported; tests import this from here
    make_compound_target_id,
    target_canonical_key,
)
from app.services.canonicalize import (
    make_target_id as _core_make_target_id,
)
from app.services.target_persist import persist_canonical_target
from integrations._retry import ServiceUnavailableError
from integrations.chembl import ChemblTarget, get_targets_for_compounds
from integrations.pubchem_bioassay import PubChemTarget, get_targets_by_inchikey
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analysis.models import PipelineConfig


def _make_target_id(uniprot_accession: str | None, gene_symbol: str) -> str:
    """Return a bare UUID v5 for a target.

    Delegates to the canonicalization core: a UniProt accession (isoform-folded)
    wins, else falls back to 'gene:{symbol}'. Byte-identical to the ETL pipeline.
    """
    return _core_make_target_id(accession=uniprot_accession, gene=gene_symbol)


class _ManualCompoundProxy:
    """Lightweight proxy that exposes DB-compound attributes for manual compounds.

    Manual compounds are never stored in the database — they arrive via the
    inject-compounds endpoint and are persisted only in stage_1._manual_compounds.
    This proxy lets the rest of stage3 treat them identically to ORM objects.
    """

    def __init__(self, data: dict) -> None:
        self.compound_id: str = data["compound_id"]
        self.canonical_name: str = data.get("canonical_name", "")
        # PubChem inchikey field is "inchikey" (no underscore) in validated dicts
        self.inchi_key: str | None = data.get("inchikey") or data.get("inchi_key")
        self.smiles: str | None = data.get("smiles") or data.get("isomeric_smiles")
        # Manual compounds have no ChEMBL ID — ChEMBL lookup will be skipped
        self.chembl_id: str | None = None


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage2 = (run.stage_results or {}).get("stage_2", {})
    # Coerce to strings: Stage 2 may emit uuid.UUID objects instead of plain strings.
    # Without this, set(compound_ids) contains UUID objects that never intersect
    # with all_covered (which holds string compound IDs from the DB), yielding
    # coverage_pct = 0% even when targets are found.
    compound_ids = [str(cid) for cid in stage2.get("all_active_compound_ids", [])]

    if not compound_ids:
        return {"covered": 0, "no_data": 0, "coverage_pct": 0.0, "targets": []}

    # Load compounds to get chembl_ids and inchi_keys — use bulk fetch
    fetched_compounds = await compound_repo.get_compounds_by_ids(session, compound_ids)

    # Fallback: if DB returned nothing, try manual compounds from stage_1 synthetic result.
    # Manual compounds (injected via T4.3) are not stored in the database — they live
    # exclusively in stage_results["stage_1"]["_manual_compounds"].
    if not fetched_compounds:
        stage1_result = (run.stage_results or {}).get("stage_1", {})
        manual_raw = stage1_result.get("_manual_compounds", [])
        if manual_raw:
            logger.debug(
                "stage3: no DB compounds found for %d compound_ids; "
                "falling back to %d manual compounds from stage_1",
                len(compound_ids),
                len(manual_raw),
            )
            # Only include compounds that are in compound_ids (safety filter)
            active_ids = set(compound_ids)
            fetched_compounds = [
                _ManualCompoundProxy(mc)
                for mc in manual_raw
                if mc.get("compound_id") in active_ids
            ]

    chembl_to_compound: dict[str, str] = {
        c.chembl_id: c.compound_id
        for c in fetched_compounds
        if c.chembl_id
    }

    # ── Stage A: ChEMBL target lookup ─────────────────────────────────────────
    chembl_results: dict[str, list[ChemblTarget]] = {}
    if chembl_to_compound:
        chembl_results = await get_targets_for_compounds(
            list(chembl_to_compound.keys()),
            min_pchembl=config.target.min_pchembl,
            human_only=config.target.human_only,
            min_assay_confidence=config.target.min_assay_confidence,
        )

    # Build gene → compound_ids mapping (ChEMBL)
    target_compound_map: dict[str, list[str]] = {}
    target_info: dict[str, ChemblTarget] = {}

    for chembl_mol_id, targets in chembl_results.items():
        compound_id = chembl_to_compound[chembl_mol_id]
        for t in targets:
            if not t.gene_symbol:
                continue
            gene = t.gene_symbol.upper()
            if gene not in target_compound_map:
                target_compound_map[gene] = []
                target_info[gene] = t
            target_compound_map[gene].append(compound_id)

    # ── Stage B: PubChem BioAssay fallback for uncovered compounds ─────────────
    # For compounds with 0 ChEMBL targets, query PubChem BioAssay by InChIKey.
    # PubChem aggregates BindingDB, ChEMBL, and 300+ bioactivity sources.
    # Citation: Kim et al. Nucleic Acids Res. 2023, 51(D1):D1373-D1380.
    covered_by_chembl: set[str] = {
        cid for cids in target_compound_map.values() for cid in cids
    }
    uncovered_compounds = [
        (c.inchi_key, c.compound_id)
        for c in fetched_compounds
        if c.compound_id not in covered_by_chembl and c.inchi_key
    ]

    pubchem_target_info: dict[str, PubChemTarget] = {}
    pubchem_ct: dict[str, set[str]] = {}  # gene -> {compound_ids from PubChem}

    # PubChem BioAssay is a non-critical FALLBACK. If it is unavailable, we keep
    # the ChEMBL data already gathered and mark the stage result as degraded —
    # we must NOT fail the run (ChEMBL outage is handled differently: unwrapped).
    pubchem_degraded = False
    pubchem_warning: dict[str, str] | None = None

    if uncovered_compounds:
        try:
            async with httpx.AsyncClient() as client:
                results = await asyncio.gather(*[
                    get_targets_by_inchikey(client, ik, human_only=config.target.human_only)
                    for ik, _ in uncovered_compounds
                ])
            # Merge inside the try so a mid-gather failure never half-merges.
            for (ik, compound_id), targets in zip(uncovered_compounds, results):
                for t in targets:
                    if not t.gene_symbol:
                        continue
                    gene = t.gene_symbol.upper()
                    # Register in PubChem-specific maps (for source-tagged CT upsert)
                    if gene not in pubchem_target_info:
                        pubchem_target_info[gene] = t
                        pubchem_ct[gene] = set()
                    pubchem_ct[gene].add(compound_id)
                    # Merge into unified target_compound_map for output
                    if gene not in target_compound_map:
                        target_compound_map[gene] = []
                    target_compound_map[gene].append(compound_id)
        except ServiceUnavailableError as exc:
            logger.warning(
                "stage3: PubChem BioAssay fallback unavailable; "
                "continuing with ChEMBL data only (degraded): %s",
                exc,
            )
            pubchem_degraded = True
            pubchem_warning = {"provider": "pubchem_bioassay", "reason": str(exc)}

    # ── Upsert Target rows (ChEMBL + PubChem) ─────────────────────────────────
    now = now_utc()

    for gene, t in target_info.items():  # ChEMBL targets
        target_id = _make_target_id(t.uniprot_accession, gene)
        canonical_key = (
            target_canonical_key(t.uniprot_accession)
            if t.uniprot_accession
            else f"gene:{gene}"
        )
        await persist_canonical_target([Target(
            target_id=target_id,
            canonical_key=canonical_key,
            gene_symbol=gene,
            uniprot_accession=t.uniprot_accession,
            retrieved_at=now,
        )], session)

    for gene, t in pubchem_target_info.items():  # PubChem targets (not in ChEMBL)
        if gene in target_info:
            continue  # Target row already upserted above
        target_id = _make_target_id(t.uniprot_accession, gene)
        canonical_key = target_canonical_key(t.uniprot_accession)
        await persist_canonical_target([Target(
            target_id=target_id,
            canonical_key=canonical_key,
            gene_symbol=gene,
            protein_name=t.protein_name,
            uniprot_accession=t.uniprot_accession,
            retrieved_at=now,
        )], session)

    await session.commit()

    # ── Upsert CompoundTarget rows ─────────────────────────────────────────────
    # ChEMBL-derived rows
    for gene, compound_id_list in target_compound_map.items():
        if gene not in target_info:
            continue  # PubChem targets handled below
        t = target_info[gene]
        target_id = _make_target_id(t.uniprot_accession, gene)
        for cid in set(compound_id_list):
            if cid in (pubchem_ct.get(gene) or set()):
                continue  # This compound+target came from PubChem, not ChEMBL
            ct_id = make_compound_target_id(cid, target_id)
            existing = await session.exec(
                select(CompoundTarget).where(CompoundTarget.compound_target_id == ct_id)
            )
            if not existing.first():
                session.add(CompoundTarget(
                    compound_target_id=ct_id,
                    compound_id=cid,
                    target_id=target_id,
                    prediction_method="chembl_bioactivity",
                    pchembl_value=t.pchembl_value,
                    retrieved_at=now,
                ))

    # PubChem-derived rows
    for gene, cid_set in pubchem_ct.items():
        t = pubchem_target_info[gene]
        target_id = _make_target_id(t.uniprot_accession, gene)
        for cid in cid_set:
            ct_id = make_compound_target_id(cid, target_id)
            existing = await session.exec(
                select(CompoundTarget).where(CompoundTarget.compound_target_id == ct_id)
            )
            if not existing.first():
                session.add(CompoundTarget(
                    compound_target_id=ct_id,
                    compound_id=cid,
                    target_id=target_id,
                    prediction_method="pubchem_bioassay",
                    pchembl_value=None,
                    retrieved_at=now,
                ))

    await session.commit()

    # ── Output ─────────────────────────────────────────────────────────────────
    # all_covered: strings from DB ORM; compound_ids: strings (coerced L71) — intersection is type-safe.
    all_covered: set[str] = {
        cid for cids in target_compound_map.values() for cid in cids
    }
    covered = len(all_covered & set(compound_ids))
    no_data = len(compound_ids) - covered
    coverage_pct = round(covered / len(compound_ids) * 100, 1) if compound_ids else 0.0

    # Build uncovered_compounds list for frontend Coverage section.
    # Includes compound_id, canonical_name, and smiles so frontend can generate
    # the STP export CSV without additional API calls.
    compound_detail: dict[str, tuple[str, str | None]] = {
        c.compound_id: (c.canonical_name, c.smiles)
        for c in fetched_compounds
    }
    uncovered_compound_list: list[dict[str, str | None]] = []
    for cid in compound_ids:
        if cid in all_covered:
            continue
        detail = compound_detail.get(cid)
        if detail is None:
            logger.warning(
                "stage3: compound_id %r not found in fetched_compounds; skipping from uncovered list",
                cid,
            )
            continue
        uncovered_compound_list.append({
            "compound_id": cid,
            "canonical_name": detail[0],
            "smiles": detail[1],
        })

    def _get_uniprot(gene: str) -> str | None:
        if gene in target_info:
            return target_info[gene].uniprot_accession or None
        if gene in pubchem_target_info:
            return pubchem_target_info[gene].uniprot_accession or None
        return None

    # Build compound → sources mapping.
    # Each compound is tagged with the source(s) that yielded targets for it.
    pubchem_covered: set[str] = {cid for cids in pubchem_ct.values() for cid in cids}
    compound_sources: dict[str, list[str]] = {}
    for cid in compound_ids:
        srcs: list[str] = []
        if cid in covered_by_chembl:
            srcs.append("chembl")
        if cid in pubchem_covered:
            srcs.append("pubchem_bioassay")
        if srcs:
            compound_sources[cid] = srcs

    enriched_targets = [
        {
            "gene_symbol": gene,
            "uniprot_id": _get_uniprot(gene),
            "compound_count": len(set(cids)),
            "compound_ids": list(set(cids)),
            # "chembl" if found via ChEMBL bioactivity; "pubchem_bioassay" if found
            # via PubChem BioAssay fallback (aggregates BindingDB + 300+ sources).
            "source": "chembl" if gene in target_info else "pubchem_bioassay",
        }
        for gene, cids in target_compound_map.items()
    ]

    result = {
        # Pipeline chain keys (Stage 4 reads these)
        "covered": covered,
        "no_data": no_data,
        "target_count": len(target_compound_map),
        "target_gene_symbols": list(target_compound_map.keys()),
        "target_compound_map": {
            gene: list(set(cids))
            for gene, cids in target_compound_map.items()
        },
        # Frontend display keys
        "coverage_pct": coverage_pct,
        "targets": enriched_targets,
        # Source tracking: compound_id → list of sources that found targets for it
        "compound_sources": compound_sources,
        # Coverage section: compounds with zero targets after ChEMBL + PubChem
        "uncovered_compounds": uncovered_compound_list,
    }

    if pubchem_degraded:
        result["degraded"] = True
        result["warning"] = pubchem_warning

    return result
