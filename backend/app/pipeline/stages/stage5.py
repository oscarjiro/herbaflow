"""Stage 5 — Overlap (candidate therapeutic targets).

Intersect the run's Stage-3 compound-target set with its Stage-4 disease-target set on the
canonical ``target_id`` (OV-2: both are FKs to ``targets.target_id``), and attach two honesty
measures: the Jaccard index (descriptive overlap magnitude) and a one-sided hypergeometric
p-value (is the overlap larger than chance?). Pure computation — no external API, NO parameters
(OV-1: background_n=20000 and alpha=0.05 are fixed, documented defaults per Methodology §5.4 +
Software Lock §2.2; a configurable background is §5.5 future work).

Result fragment (``stage_results["5"]``); ``count`` is the overlap size (0 -> terminal hard-stop,
OV-4, handled by the engine):
  - ``overlap``: [{target_id, gene_symbol, uniprot_accession, opentargets_score}]
  - ``count``/``compound_target_count``/``disease_target_count``/``union_count``/``jaccard``
  - ``hypergeometric``: {background_n, K, n, k, p_value, alpha, significant}
  - ``unmapped_count`` (overlap targets with no gene_symbol -> can't go to STRING/g:Profiler)
  - ``flags`` (``non_significant_overlap`` / ``unmapped_targets``)
"""

from __future__ import annotations

import logging
from typing import Any

from scipy.stats import hypergeom
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("herbaflow.pipeline")

BACKGROUND_N = 20000  # human protein-coding gene count (Methodology §5.4 default)
ALPHA = 0.05  # conventional significance threshold (Methodology §5.4 default)


def compute(stage3: dict[str, Any], stage4: dict[str, Any]) -> dict[str, Any]:
    """Pure overlap math from the Stage-3 and Stage-4 stored results.

    Both sides are the edit-layer ``targets`` list (Stage 4 no longer keeps a separate
    ``disease_targets`` view — B-DUP-2/L-11). The overlap is built on the EFFECTIVE sets: rows
    tagged ``"user-removed"`` are excluded on BOTH sides, so the intersection reflects what the
    user actually has now (and S3/S4 stay symmetric). Untagged rows (raw computed / fixtures) have
    no ``tag`` and are kept. The disease association score rides on each S4 row.
    """
    s3_targets = {
        t["target_id"]: t for t in stage3.get("targets", []) if t.get("tag") != "user-removed"
    }
    s4_targets = {
        t["target_id"]: t for t in stage4.get("targets", []) if t.get("tag") != "user-removed"
    }
    a_ids = set(s3_targets)
    b_ids = set(s4_targets)
    overlap_ids = a_ids & b_ids
    union = a_ids | b_ids

    overlap: list[dict[str, Any]] = []
    for tid in sorted(overlap_ids):
        s4_row = s4_targets[tid]
        s3_row = s3_targets[tid]
        overlap.append(
            {
                "target_id": tid,
                "gene_symbol": s4_row.get("gene_symbol") or s3_row.get("gene_symbol"),
                "uniprot_accession": s4_row.get("uniprot_accession")
                or s3_row.get("uniprot_accession"),
                "opentargets_score": s4_row.get("opentargets_score"),
            }
        )

    jaccard = (len(overlap_ids) / len(union)) if union else 0.0

    # One-sided hypergeometric P(X >= k): sf(k-1) = P(X > k-1). Clamp the degenerate
    # K>N or n>N (should not occur at N=20000); flag if clamped.
    big_n = BACKGROUND_N
    k_disease = min(len(b_ids), big_n)
    n_compound = min(len(a_ids), big_n)
    k = len(overlap_ids)
    p_value = float(hypergeom.sf(k - 1, big_n, k_disease, n_compound)) if k > 0 else 1.0
    significant = p_value < ALPHA

    unmapped = sum(1 for o in overlap if not o["gene_symbol"])
    flags: list[str] = []
    if k > 0 and not significant:
        flags.append("non_significant_overlap")
    if unmapped:
        flags.append("unmapped_targets")
    if len(b_ids) > big_n or len(a_ids) > big_n:
        flags.append("set_exceeds_background")

    return {
        "overlap": overlap,
        "count": k,
        "compound_target_count": len(a_ids),
        "disease_target_count": len(b_ids),
        "union_count": len(union),
        "jaccard": round(jaccard, 6),
        "hypergeometric": {
            "background_n": big_n,
            "K": len(b_ids),
            "n": len(a_ids),
            "k": k,
            "p_value": p_value,
            "alpha": ALPHA,
            "significant": significant,
        },
        "unmapped_count": unmapped,
        "state": "computed",
        "flags": flags,
    }


async def run(session: AsyncSession | None, run: Any) -> dict[str, Any]:
    """Compute the overlap from the run's stored Stage-3 and Stage-4 results.

    Pure read of ``stage_results`` — the gene info needed downstream already rides on those
    fragments (S3 and S4 both expose an edit-layer ``targets`` list carrying gene_symbol/
    uniprot_accession, and S4 rows also carry the disease association ``score``), so no DB
    round-trip is required (OV-2). ``compute`` filters out ``user-removed`` rows on both sides.
    ``session`` is accepted for runner-signature symmetry.
    """
    stage3 = run.stage_results["3"]
    stage4 = run.stage_results["4"]
    result = compute(stage3, stage4)
    logger.info(
        "stage 5: %d overlap of %d compound / %d disease targets (J=%.4f, p=%.2e, sig=%s)",
        result["count"],
        result["compound_target_count"],
        result["disease_target_count"],
        result["jaccard"],
        result["hypergeometric"]["p_value"],
        result["hypergeometric"]["significant"],
    )
    return result
