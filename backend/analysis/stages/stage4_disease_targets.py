"""Stage 4 — Disease-associated targets.

Resolves the gene targets associated with the analysis' disease(s). For a single
disease this is a direct lookup; for multiple diseases the per-disease target
sets are combined by **union** (a gene is retained if it is associated with
*any* selected disease), keyed by uppercased gene symbol.

Multi-disease aggregation rules:
- **Union, not intersection.** Selecting several diseases (e.g. T2DM plus its
  comorbidities) broadens the target space rather than narrowing it. This
  matches the standard network-pharmacology treatment of multi-indication /
  comorbidity studies, where the disease module is the union of each condition's
  associated genes (Hopkins 2008, Nat Chem Biol 4:682; Li & Zhang 2013, Chin J
  Nat Med 11:110). Intersection would discard disease-specific targets and is
  only appropriate when the explicit question is "shared targets across all
  diseases".
- **Score = max across diseases.** When a gene is associated with more than one
  selected disease, the strongest (highest) association score is kept so the
  gene is represented by its best evidence. Every contributing disease is still
  recorded in the per-target ``diseases`` list (disease_id, disease_name,
  association_score) for downstream attribution, and
  ``disease_gene_symbols_by_disease`` preserves the unmerged per-disease
  breakdown consumed by Stage 5.

Sources, in priority order: cached ``disease_targets`` rows (min_score filtered)
first, falling back to the Open Targets API per disease only when the cache is
empty. A separate ``manual_targets`` input mode bypasses both and uses an
injected gene list directly.
"""

from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import disease_repo


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    params = run.parameters or {}

    # Manual disease targets mode: bypass Open Targets, use injected gene list
    if params.get("_disease_input_mode") == "manual_targets":
        from app.services import gene_symbols

        injected = params.get("_injected_disease_targets", [])
        if not injected:
            return {
                "disease_target_count": 0,
                "targets": [],
                "disease_gene_symbols": [],
                "disease_gene_symbols_by_disease": {},
                "normalization": {"changed": [], "unrecognized": []},
            }

        results = gene_symbols.normalize_many(
            g for g in injected if isinstance(g, str) and g.strip()
        )
        changed = [
            {"from": r.input, "to": r.canonical}
            for r in results
            if r.status != "unrecognized" and r.canonical != r.input.upper()
        ]
        unrecognized = [r.input for r in results if r.status == "unrecognized"]

        # Deduplicate canonical symbols while preserving first-seen order
        unique_genes = list(dict.fromkeys(r.canonical for r in results if r.canonical))
        targets = [
            {
                "gene_symbol": gene,
                "uniprot_accession": None,
                "score": None,
                "disease_name": "Manual input",
                "source": "user_provided",
            }
            for gene in unique_genes
        ]
        return {
            "disease_target_count": len(targets),
            "targets": targets,
            "disease_gene_symbols": unique_genes,
            "disease_gene_symbols_by_disease": {"manual": unique_genes},
            "normalization": {"changed": changed, "unrecognized": unrecognized},
        }

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
                        "uniprot_accession": target.uniprot_accession or "",
                        "score": score,
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
                    if not any(d["disease_id"] == did for d in existing["diseases"]):
                        existing["diseases"].append(
                            {
                                "disease_id": did,
                                "disease_name": disease.disease_name,
                                "association_score": score,
                            }
                        )
                    if score > existing["score"]:
                        existing["score"] = score
        else:
            # Fallback: Open Targets API
            from integrations.open_targets import get_disease_targets
            ontology_id = disease.ontology_id or ""
            ot_targets = await get_disease_targets(
                ontology_id, min_score=config.disease_targets.min_score
            )
            for t in ot_targets:
                gene = (t.gene_symbol or "").upper()
                if not gene:
                    continue
                disease_gene_symbols_by_disease[did].append(gene)
                if gene not in all_targets:
                    all_targets[gene] = {
                        "gene_symbol": gene,
                        "uniprot_accession": "",
                        "score": t.score,
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
                    if not any(d["disease_id"] == did for d in existing["diseases"]):
                        existing["diseases"].append(
                            {
                                "disease_id": did,
                                "disease_name": disease.disease_name,
                                "association_score": t.score,
                            }
                        )
                    if t.score > existing["score"]:
                        existing["score"] = t.score

    return {
        "disease_target_count": len(all_targets),
        "disease_gene_symbols": list(all_targets.keys()),
        "disease_gene_symbols_by_disease": disease_gene_symbols_by_disease,
        "targets": list(all_targets.values()),
    }
