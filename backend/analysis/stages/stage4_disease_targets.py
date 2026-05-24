from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import disease_repo


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    params = run.parameters or {}
    disease_ids = params.get("_disease_ids", [])

    all_targets: dict[str, dict] = {}

    for did in disease_ids:
        disease = await disease_repo.get_disease_by_id(session, did)
        if not disease:
            continue

        db_targets = await disease_repo.get_targets_for_disease(
            session, did, min_score=config.disease_targets.min_score
        )

        if db_targets:
            for target, score in db_targets:
                gene = (target.gene_symbol or "").upper()
                if gene and gene not in all_targets:
                    all_targets[gene] = {
                        "gene_symbol": gene,
                        "uniprot_id": target.uniprot_accession or "",
                        "score": score,
                        "disease_name": disease.disease_name,
                        "source": "db_cache",
                    }
        else:
            # Fallback: Open Targets API
            from integrations.open_targets import get_disease_targets
            ontology_id = disease.ontology_id or ""
            ot_targets = await get_disease_targets(
                ontology_id, min_score=config.disease_targets.min_score
            )
            for t in ot_targets:
                gene = t.gene_symbol.upper()
                if gene not in all_targets:
                    all_targets[gene] = {
                        "gene_symbol": gene,
                        "uniprot_id": "",
                        "association_score": t.score,
                        "disease_name": disease.disease_name,
                        "source": "open_targets_api",
                    }

    return {
        "disease_target_count": len(all_targets),
        "disease_gene_symbols": list(all_targets.keys()),
        "targets": list(all_targets.values()),
    }
