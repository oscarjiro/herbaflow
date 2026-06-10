"""Stage 4 — disease→target collection (DB read of the ETL-seeded Open Targets snapshot).

Open Targets is an ETL-time source (like KNApSAcK on the compound side): the seeded
``disease_targets`` table already holds each seeded disease's evidence-graded associations.
So Step 4 is a filtered database read — NOT a live API call. There is no external client, no
DOID->EFO bridge, no outage handling, and NO write (the disease-target relationship does not
persist per analysis; §6.2-E).

Output (uniform entity-stage shape; the engine's edit-layer fold tags ``targets`` and overwrites
``count``/``state``):
  - ``targets``:         entity list ``[{target_id, canonical_name}]`` for the edit layer.
  - ``disease_targets``: per-row view data ``[{target_id, gene_symbol, uniprot_accession, score,
                          association_type, source_url}]`` carrying the association score (DT4-9).
  - ``count`` / ``state`` / ``min_score_applied``.

An empty side (filter too strict / thin coverage) parks the run at the Step-4 checkpoint with a
``count`` 0 honesty flag; in guided mode the engine **refuses Approve & Continue** until the user
recovers by lowering ``min_score`` (Redo) or adding a manual target. In auto mode an empty side is a
hard-stop (don't waste downstream). The terminal scientific hard-stop is still S5 (0 overlap) (B6).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.disease_target import DiseaseTargetRepository

logger = logging.getLogger("herbaflow.pipeline")


def compute(rows: list[dict[str, Any]], min_score: float) -> dict[str, Any]:
    """Pure shape: rows (from the repo read) -> the stored Stage-4 result fragment."""
    targets = [
        {
            "target_id": r["target_id"],
            "canonical_name": r["gene_symbol"] or r["uniprot_accession"] or r["target_id"],
        }
        for r in rows
    ]
    disease_targets = [
        {
            "target_id": r["target_id"],
            "gene_symbol": r["gene_symbol"],
            "uniprot_accession": r["uniprot_accession"],
            "score": r["score"],
            "association_type": r["association_type"],
            "source_url": r["source_url"],
        }
        for r in rows
    ]
    return {
        "targets": targets,
        "disease_targets": disease_targets,
        "count": len(targets),
        "min_score_applied": min_score,
        "state": "computed",
    }


async def run(
    session: AsyncSession, disease_id: uuid.UUID, params: dict[str, Any]
) -> dict[str, Any]:
    """Read the seeded disease-targets at ``min_score`` and shape them.

    No external call, no write.
    """
    repo = DiseaseTargetRepository(session)
    min_score = float(params["min_score"])
    rows = await repo.targets_for_disease(disease_id, min_score)
    logger.info(
        "stage 4: %d disease-target(s) for disease %s at min_score %.2f",
        len(rows),
        str(disease_id)[:8],
        min_score,
    )
    return compute(rows, min_score)
