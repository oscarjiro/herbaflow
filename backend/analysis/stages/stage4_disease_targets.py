"""Stage 4 — Disease-associated targets.

Resolves the gene targets associated with the analysis' single disease from the
cached ``disease_targets`` rows (``min_score`` filtered). A separate
``manual_targets`` input mode bypasses the lookup and uses an injected gene list
directly (no disease).

Exactly one disease per analysis: the disease id/name are emitted once at the
stage level; each target row carries only ``gene_symbol``, ``uniprot_accession``,
``score`` and ``source``.
"""

from app.models.analysis import AnalysisRun
from app.repositories import disease_repo
from sqlmodel.ext.asyncio.session import AsyncSession

from analysis.models import PipelineConfig


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    params = run.parameters or {}

    # Manual disease targets mode: bypass Open Targets, use injected target list.
    # _injected_disease_targets is resolved at create time (app.routers.analyses →
    # resolve_targets) and stored as a list of resolved DICTS, each carrying
    # gene_symbol / uniprot_id / sources. Normalization already happened upstream,
    # so this branch just reads the dicts (no offline normalize here).
    if params.get("_disease_input_mode") == "manual_targets":
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

        # Coerce each element to the resolved-dict shape. The create path always
        # stores dicts now; a plain string is a legacy/unexpected shape — treat it
        # as a symbol-only target (uppercased) so we never crash on bad input.
        def _as_dict(el) -> dict | None:
            if isinstance(el, dict):
                return el
            if isinstance(el, str) and el.strip():
                return {"gene_symbol": el.strip().upper(), "sources": []}
            return None

        coerced = [d for d in (_as_dict(e) for e in injected) if d]

        targets: list[dict] = []
        seen: set[str] = set()
        for d in coerced:
            gene = d.get("gene_symbol")
            if not gene or gene in seen:
                continue
            seen.add(gene)
            targets.append({
                "gene_symbol": gene,
                "uniprot_accession": d.get("uniprot_id"),
                "score": None,
                "source": "user_provided",
            })

        unique_genes = [t["gene_symbol"] for t in targets]
        unrecognized = [
            d["gene_symbol"]
            for d in coerced
            if "manual_unrecognized" in d.get("sources", []) and d.get("gene_symbol")
        ]
        return {
            "disease_id": None,
            "disease_name": None,
            "disease_target_count": len(targets),
            "disease_gene_symbols": unique_genes,
            "targets": targets,
            "state": "user_provided",
            "inputs": {
                # Normalization happened at create time; nothing rejected here.
                "rejected": [],
                "normalized": [],
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
                "uniprot_accession": target.uniprot_accession or None,
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
