import uuid
from datetime import datetime
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from app.models.target import Target, CompoundTarget
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import compound_repo
from integrations.chembl import get_targets_for_compounds, ChemblTarget

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


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage2 = (run.stage_results or {}).get("stage_2", {})
    compound_ids = stage2.get("all_active_compound_ids", [])

    if not compound_ids:
        return {"covered": 0, "no_data": 0, "coverage_pct": 0.0, "targets": []}

    # Load compounds to get chembl_ids — use bulk fetch
    fetched_compounds = await compound_repo.get_compounds_by_ids(session, compound_ids)
    chembl_to_compound: dict[str, str] = {
        c.chembl_id: c.compound_id
        for c in fetched_compounds
        if c.chembl_id
    }

    # Fetch targets from ChEMBL
    chembl_results: dict[str, list[ChemblTarget]] = {}
    if chembl_to_compound:
        chembl_results = await get_targets_for_compounds(
            list(chembl_to_compound.keys()),
            min_pchembl=config.target.min_pchembl,
            human_only=config.target.human_only,
        )

    # Build gene -> compound_ids mapping
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

    # Upsert Target rows
    now = datetime.utcnow()
    for gene, t in target_info.items():
        target_id = _make_target_id(t.uniprot_accession, gene)
        existing = await session.exec(select(Target).where(Target.target_id == target_id))
        if not existing.first():
            # canonical_key must match the key used to generate target_id —
            # same convention as etl/disease_targets/utils.py canonical_key_for_target().
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

    await session.commit()

    # Upsert CompoundTarget rows
    for gene, compound_id_list in target_compound_map.items():
        t = target_info[gene]
        target_id = _make_target_id(t.uniprot_accession, gene)
        for cid in set(compound_id_list):
            ct_id = _make_ct_id(cid, target_id)
            existing = await session.exec(select(CompoundTarget).where(CompoundTarget.compound_target_id == ct_id))
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
    await session.commit()

    covered = len(set(chembl_to_compound.values()) & {
        cid for cids in target_compound_map.values() for cid in cids
    })
    no_data = len(compound_ids) - covered
    coverage_pct = round(covered / len(compound_ids) * 100, 1) if compound_ids else 0.0

    enriched_targets = [
        {
            "gene_symbol": gene,
            "uniprot_id": target_info[gene].uniprot_accession or "",
            "compound_count": len(set(cids)),
            "compound_ids": list(set(cids)),
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
            gene: list(cids)
            for gene, cids in target_compound_map.items()
        },
        # Frontend display keys
        "coverage_percent": coverage_pct,
        "targets": enriched_targets,
    }
