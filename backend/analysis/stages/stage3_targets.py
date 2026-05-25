import asyncio
import logging
import uuid
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from app.models.target import Target, CompoundTarget
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import compound_repo
from integrations.chembl import get_targets_for_compounds, ChemblTarget
from integrations.pubchem_bioassay import get_targets_by_inchikey, PubChemTarget

# UUID v5 namespaces — TARGET_NS must match etl/disease_targets/utils.py exactly.
# Replicated here because the backend cannot import from etl/.
# Derivation: uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.targets")
TARGET_NS: uuid.UUID = uuid.UUID("421e4557-e00d-533d-ab26-5f7b761b9483")
# Derivation: uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.compound_targets")
# ETL does not produce compound_targets; this namespace is backend-only for
# the ChEMBL-derived compound–target join table.
COMPOUND_TARGET_NS: uuid.UUID = uuid.UUID("59a665ef-1743-5e45-98c2-128fe7e345a9")


def _make_target_id(uniprot_accession: str | None, gene_symbol: str) -> str:
    """Return a bare UUID v5 for a target.

    Uses canonical_key format matching the ETL disease_targets pipeline:
    'uniprot:{acc}' when a UniProt accession is available, else falls back
    to 'gene:{symbol}' for ChEMBL-only targets without a UniProt ID.
    """
    if uniprot_accession:
        key = f"uniprot:{uniprot_accession.strip()}"
    else:
        key = f"gene:{gene_symbol.upper()}"
    return str(uuid.uuid5(TARGET_NS, key))


def _make_ct_id(compound_id: str, target_id: str) -> str:
    """Return a bare UUID v5 for a compound–target association."""
    return str(uuid.uuid5(COMPOUND_TARGET_NS, f"{compound_id}:{target_id}"))


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
    compound_ids = stage2.get("all_active_compound_ids", [])

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

    if uncovered_compounds:
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(*[
                get_targets_by_inchikey(client, ik, human_only=config.target.human_only)
                for ik, _ in uncovered_compounds
            ])
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

    # ── Upsert Target rows (ChEMBL + PubChem) ─────────────────────────────────
    now = datetime.utcnow()

    for gene, t in target_info.items():  # ChEMBL targets
        target_id = _make_target_id(t.uniprot_accession, gene)
        existing = await session.exec(select(Target).where(Target.target_id == target_id))
        if not existing.first():
            canonical_key = (
                f"uniprot:{t.uniprot_accession.strip()}"
                if t.uniprot_accession
                else f"gene:{gene}"
            )
            session.add(Target(
                target_id=target_id,
                canonical_key=canonical_key,
                gene_symbol=gene,
                uniprot_accession=t.uniprot_accession,
                organism_tax_id=9606,
                retrieved_at=now,
            ))

    for gene, t in pubchem_target_info.items():  # PubChem targets (not in ChEMBL)
        if gene in target_info:
            continue  # Target row already upserted above
        target_id = _make_target_id(t.uniprot_accession, gene)
        existing = await session.exec(select(Target).where(Target.target_id == target_id))
        if not existing.first():
            canonical_key = f"uniprot:{t.uniprot_accession.strip()}"
            session.add(Target(
                target_id=target_id,
                canonical_key=canonical_key,
                gene_symbol=gene,
                protein_name=t.protein_name,
                uniprot_accession=t.uniprot_accession,
                organism_tax_id=9606,
                retrieved_at=now,
            ))

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
            ct_id = _make_ct_id(cid, target_id)
            existing = await session.exec(
                select(CompoundTarget).where(CompoundTarget.compound_target_id == ct_id)
            )
            if not existing.first():
                session.add(CompoundTarget(
                    compound_target_id=ct_id,
                    compound_id=cid,
                    target_id=target_id,
                    prediction_method="chembl_bioactivity",
                    evidence_type="experimental",
                    pchembl_value=t.pchembl_value,
                    retrieved_at=now,
                ))

    # PubChem-derived rows
    for gene, cid_set in pubchem_ct.items():
        t = pubchem_target_info[gene]
        target_id = _make_target_id(t.uniprot_accession, gene)
        for cid in cid_set:
            ct_id = _make_ct_id(cid, target_id)
            existing = await session.exec(
                select(CompoundTarget).where(CompoundTarget.compound_target_id == ct_id)
            )
            if not existing.first():
                session.add(CompoundTarget(
                    compound_target_id=ct_id,
                    compound_id=cid,
                    target_id=target_id,
                    prediction_method="pubchem_bioassay",
                    evidence_type="experimental",
                    pchembl_value=None,
                    retrieved_at=now,
                ))

    await session.commit()

    # ── Output ─────────────────────────────────────────────────────────────────
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

    def _get_uniprot(gene: str) -> str:
        if gene in target_info:
            return target_info[gene].uniprot_accession or ""
        if gene in pubchem_target_info:
            return pubchem_target_info[gene].uniprot_accession or ""
        return ""

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

    return {
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
