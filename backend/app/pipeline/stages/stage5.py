"""Stage 5 — Overlap (candidate therapeutic targets).

Intersect the run's Stage-3 compound-target set with its Stage-4 disease-target set on the
canonical ``target_id`` (OV-2: both are FKs to ``targets.target_id``). Pure set intersection —
the field-standard raw overlap (as Venny/jvenn produce); no statistics, no parameters, no
external API.

Result fragment (``stage_results["5"]``); ``count`` is the overlap size (0 -> terminal hard-stop,
OV-4, handled by the engine):
  - ``overlap``: [{target_id, gene_symbol, uniprot_accession, opentargets_score}]
  - ``count`` (|A ∩ B|) / ``compound_target_count`` (|A|) / ``disease_target_count`` (|B|)
  - ``unmapped_count`` (overlap targets with no gene_symbol -> can't go to STRING/g:Profiler)
  - ``flags`` (``unmapped_targets``)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("herbaflow.pipeline")


def compute(stage3: dict[str, Any], stage4: dict[str, Any]) -> dict[str, Any]:
    """Pure set intersection of the Stage-3 and Stage-4 stored target lists.

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

    unmapped = sum(1 for o in overlap if not o["gene_symbol"])
    flags: list[str] = []
    if unmapped:
        flags.append("unmapped_targets")

    return {
        "overlap": overlap,
        "count": len(overlap_ids),
        "compound_target_count": len(a_ids),
        "disease_target_count": len(b_ids),
        "unmapped_count": unmapped,
        "state": "computed",
        "flags": flags,
    }


async def run(session: AsyncSession | None, run: Any) -> dict[str, Any]:
    """Compute the overlap from the run's stored Stage-3 and Stage-4 results.

    Pure read of ``stage_results`` — the gene info needed downstream already rides on those
    fragments (S3 and S4 both expose an edit-layer ``targets`` list carrying gene_symbol/
    uniprot_accession, and S4 rows also carry the disease association ``opentargets_score``), so no
    DB round-trip is required (OV-2). ``compute`` filters out ``user-removed`` rows on both sides.
    ``session`` is accepted for runner-signature symmetry.
    """
    stage3 = run.stage_results["3"]
    stage4 = run.stage_results["4"]
    result = compute(stage3, stage4)
    logger.info(
        "stage 5: %d overlap of %d compound / %d disease targets",
        result["count"],
        result["compound_target_count"],
        result["disease_target_count"],
    )
    return result
