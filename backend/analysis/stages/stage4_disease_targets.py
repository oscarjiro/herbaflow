from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import disease_repo


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    params = run.parameters or {}
    disease_ids = params.get("_disease_ids", [])

    # gene → merged target dict; tracks all source diseases per gene
    all_targets: dict[str, dict] = {}
    # disease_id → list of gene symbols for per-disease Stage 5 breakdown
    disease_gene_symbols_by_disease: dict[str, list[str]] = {}

    for did in disease_ids:
        disease = await disease_repo.get_disease_by_id(session, did)
        if not disease:
            continue

        disease_gene_symbols_by_disease[did] = []

        db_targets = await disease_repo.get_targets_for_disease(
            session, did, min_score=config.disease_targets.min_score
        )

        if db_targets:
            for target, score in db_targets:
                gene = (target.gene_symbol or "").upper()
                if not gene:
                    continue
                disease_gene_symbols_by_disease[did].append(gene)
                if gene not in all_targets:
                    all_targets[gene] = {
                        "gene_symbol": gene,
                        "uniprot_id": target.uniprot_accession or "",
                        "association_score": score,
                        "disease_name": disease.disease_name,
                        "source": "db_cache",
                        "diseases": [
                            {
                                "disease_id": did,
                                "disease_name": disease.disease_name,
                                "association_score": score,
                            }
                        ],
                    }
                else:
                    existing = all_targets[gene]
                    existing["diseases"].append(
                        {
                            "disease_id": did,
                            "disease_name": disease.disease_name,
                            "association_score": score,
                        }
                    )
                    if score > existing["association_score"]:
                        existing["association_score"] = score
        else:
            # Fallback: Open Targets API
            from integrations.open_targets import get_disease_targets
            ontology_id = disease.ontology_id or ""
            ot_targets = await get_disease_targets(
                ontology_id, min_score=config.disease_targets.min_score
            )
            for t in ot_targets:
                gene = t.gene_symbol.upper()
                disease_gene_symbols_by_disease[did].append(gene)
                if gene not in all_targets:
                    all_targets[gene] = {
                        "gene_symbol": gene,
                        "uniprot_id": "",
                        "association_score": t.score,
                        "disease_name": disease.disease_name,
                        "source": "open_targets_api",
                        "diseases": [
                            {
                                "disease_id": did,
                                "disease_name": disease.disease_name,
                                "association_score": t.score,
                            }
                        ],
                    }
                else:
                    existing = all_targets[gene]
                    existing["diseases"].append(
                        {
                            "disease_id": did,
                            "disease_name": disease.disease_name,
                            "association_score": t.score,
                        }
                    )
                    if t.score > existing["association_score"]:
                        existing["association_score"] = t.score

    return {
        "disease_target_count": len(all_targets),
        "disease_gene_symbols": list(all_targets.keys()),
        "disease_gene_symbols_by_disease": disease_gene_symbols_by_disease,
        "targets": list(all_targets.values()),
    }
