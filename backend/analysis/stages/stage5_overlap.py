from scipy.stats import hypergeom
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession

# Universe for the Stage 5 overlap hypergeometric test: ~20,000 human protein-coding
# genes. This is the proteome population for the overlap test ONLY — it is distinct from
# the Stage 8 enrichment background (the Stage-3 compound-target set). Deliberate; keep.
HUMAN_PROTEOME_SIZE = 20_000


def compute_overlap(
    compound_genes: set[str],
    disease_genes: set[str],
    population_size: int = HUMAN_PROTEOME_SIZE,
) -> dict:
    overlap = compound_genes & disease_genes
    union = compound_genes | disease_genes

    overlap_count = len(overlap)
    union_count = len(union)
    compound_only_count = len(compound_genes) - overlap_count
    disease_only_count = len(disease_genes) - overlap_count

    jaccard = overlap_count / union_count if union_count > 0 else 0.0

    p_value = 1.0
    if overlap_count > 0 and compound_genes and disease_genes:
        rv = hypergeom(
            M=population_size,
            n=len(disease_genes),
            N=len(compound_genes),
        )
        p_value = float(rv.sf(overlap_count - 1))

    # Single-disease enforcement => exactly one overlap test per run. One test has no
    # multiplicity, so the raw p-value needs no multiple-testing correction. The fields
    # below mark it explicitly as a single uncorrected exploratory test so the UI does
    # not present it with more rigor than a lone hypergeometric test warrants.
    return {
        "overlap": sorted(overlap),
        "overlap_count": overlap_count,
        "compound_only_count": compound_only_count,
        "disease_only_count": disease_only_count,
        "jaccard": round(jaccard, 4),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
        "n_tests": 1,
        "correction": "none",
        "exploratory": True,
        "venn": {
            "compound_only": compound_only_count,
            "overlap": overlap_count,
            "disease_only": disease_only_count,
        },
    }


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage3 = (run.stage_results or {}).get("stage_3", {})
    stage4 = (run.stage_results or {}).get("stage_4", {})

    compound_genes = set(stage3.get("target_gene_symbols", []))
    disease_genes = set(stage4.get("disease_gene_symbols", []))

    return compute_overlap(compound_genes, disease_genes)
