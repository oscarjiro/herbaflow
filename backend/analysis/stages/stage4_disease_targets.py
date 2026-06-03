"""Stage 4 — Disease-associated targets.

Resolves the gene targets associated with the analysis' single disease from the
cached ``disease_targets`` rows (``min_score`` filtered). A separate
``manual_targets`` input mode bypasses the lookup and uses an injected gene list
directly (no disease).

Exactly one disease per analysis: the disease id/name are emitted once at the
stage level; each target row carries only ``gene_symbol``, ``uniprot_accession``,
``score`` and ``source``.
"""

from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import disease_repo


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    params = run.parameters or {}

    # Manual disease targets mode: bypass Open Targets, use injected gene list.
    if params.get("_disease_input_mode") == "manual_targets":
        from app.services import gene_symbols

        injected = params.get("_injected_disease_targets", [])
        if not injected:
            return {
                "disease_id": None,
                "disease_name": None,
                "disease_target_count": 0,
                "disease_gene_symbols": [],
                "targets": [],
                "state": "user_provided",
                "inputs": {"rejected": [], "normalized": [], "unrecognized": []},
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

        unique_genes = list(dict.fromkeys(r.canonical for r in results if r.canonical))
        targets = [
            {
                "gene_symbol": gene,
                "uniprot_accession": None,
                "score": None,
                "source": "user_provided",
            }
            for gene in unique_genes
        ]
        return {
            "disease_id": None,
            "disease_name": None,
            "disease_target_count": len(targets),
            "disease_gene_symbols": unique_genes,
            "targets": targets,
            "state": "user_provided",
            "inputs": {
                "rejected": [],
                "normalized": changed,
                "unrecognized": unrecognized,
            },
        }

    disease_id = params.get("_disease_id")
    if not disease_id:
        return {
            "disease_id": None,
            "disease_name": None,
            "disease_target_count": 0,
            "disease_gene_symbols": [],
            "targets": [],
            "state": "computed",
        }

    disease = await disease_repo.get_disease_by_id(session, disease_id)
    if not disease:
        return {
            "disease_id": disease_id,
            "disease_name": None,
            "disease_target_count": 0,
            "disease_gene_symbols": [],
            "targets": [],
            "state": "computed",
        }

    targets: list[dict] = []
    seen: set[str] = set()

    db_targets = await disease_repo.get_targets_for_disease(
        session, disease_id, min_score=config.disease_targets.min_score
    )

    if db_targets:
        for target, score in db_targets:
            gene = (target.gene_symbol or "").upper()
            if not gene or gene in seen:
                continue
            seen.add(gene)
            targets.append({
                "gene_symbol": gene,
                "uniprot_accession": target.uniprot_accession or "",
                "score": score,
                "source": "db_cache",
            })

    return {
        "disease_id": disease_id,
        "disease_name": disease.disease_name,
        "disease_target_count": len(targets),
        "disease_gene_symbols": [t["gene_symbol"] for t in targets],
        "targets": targets,
        "state": "computed",
    }
