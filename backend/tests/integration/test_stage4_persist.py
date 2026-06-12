"""Integration: stage4.run reads exactly the filtered rows and writes NOTHING."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.pipeline.stages import stage4


async def _seed(session, did, rows):
    await session.execute(
        text(
            "insert into diseases(disease_id, canonical_key, disease_name) "
            "values (:d,'doid:s4','S4 Disease') on conflict do nothing"
        ),
        {"d": did},
    )
    for gene, acc, score in rows:
        tid = uuid.uuid4()
        await session.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol, uniprot_accession) "
                "values (:t,:k,:g,:a)"
            ),
            {"t": tid, "k": f"uniprot:{acc}", "g": gene, "a": acc},
        )
        await session.execute(
            text(
                "insert into disease_targets"
                "(disease_target_id, disease_id, target_id, association_type, score) "
                "values (:i,:d,:t,'overall',:s)"
            ),
            {"i": uuid.uuid4(), "d": did, "t": tid, "s": score},
        )
    await session.flush()


@pytest.mark.asyncio
async def test_stage4_reads_filtered_rows_and_writes_nothing(session):
    did = uuid.uuid4()
    await _seed(session, did, [("GA", "P11111", 0.9), ("GB", "P22222", 0.4), ("GC", "P33333", 0.2)])

    before = (await session.execute(text("select count(*) from disease_targets"))).scalar_one()

    result = await stage4.run(session, did, {"min_score": 0.3})
    await session.flush()

    assert result["count"] == 2
    assert "disease_targets" not in result  # one enriched targets list now (B-DUP-2/L-11)
    assert [t["gene_symbol"] for t in result["targets"]] == ["GA", "GB"]
    # No new disease_targets rows written by Stage 4 (read-only).
    after = (await session.execute(text("select count(*) from disease_targets"))).scalar_one()
    assert after == before
