"""Integration: DiseaseTargetRepository filtered read + count against real Postgres."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.repositories.disease_target import DiseaseTargetRepository


async def _seed(session, disease_id, rows):
    """rows: list of (gene_symbol, accession, score | None)."""
    await session.execute(
        text(
            "insert into diseases(disease_id, canonical_key, disease_name) "
            "values (:d, 'doid:dt', 'DT Disease') on conflict do nothing"
        ),
        {"d": disease_id},
    )
    for gene, acc, score in rows:
        tid = uuid.uuid4()
        await session.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol, "
                "uniprot_accession, source_url) "
                "values (:t, :k, :g, :a, :u)"
            ),
            {
                "t": tid,
                "k": f"uniprot:{acc}",
                "g": gene,
                "a": acc,
                "u": f"https://www.uniprot.org/uniprotkb/{acc}/entry",
            },
        )
        await session.execute(
            text(
                "insert into disease_targets"
                "(disease_target_id, disease_id, target_id, association_type, score, source_url) "
                "values (:i, :d, :t, 'overall', :s, :u)"
            ),
            {
                "i": uuid.uuid4(),
                "d": disease_id,
                "t": tid,
                "s": score,
                "u": f"https://platform.opentargets.org/disease/{acc}",
            },
        )
    await session.flush()


@pytest.mark.asyncio
async def test_filtered_read_orders_by_score_and_joins_targets(session):
    did = uuid.uuid4()
    await _seed(
        session,
        did,
        [
            ("GENEA", "P11111", 0.9),
            ("GENEB", "P22222", 0.4),
            ("GENEC", "P33333", 0.2),
            ("GENED", "P44444", None),
        ],
    )
    repo = DiseaseTargetRepository(session)

    rows = await repo.targets_for_disease(did, 0.3)
    # 0.2 filtered out, NULL filtered out, ordered desc.
    assert [r["gene_symbol"] for r in rows] == ["GENEA", "GENEB"]
    assert rows[0]["score"] == 0.9
    assert rows[0]["uniprot_accession"] == "P11111"
    assert rows[0]["association_type"] == "overall"
    assert rows[0]["source_url"].endswith("/P11111/entry")  # the TARGET (UniProt) link
    assert all("target_id" in r for r in rows)

    # Raising the floor re-filters to fewer.
    assert [r["gene_symbol"] for r in await repo.targets_for_disease(did, 0.5)] == ["GENEA"]
    # min_score above the max -> empty (no hard error).
    assert await repo.targets_for_disease(did, 0.99) == []


@pytest.mark.asyncio
async def test_count_for_disease_matches_filter(session):
    did = uuid.uuid4()
    await _seed(
        session, did, [("GENEA", "P11111", 0.9), ("GENEB", "P22222", 0.4), ("GENEC", "P33333", 0.2)]
    )
    repo = DiseaseTargetRepository(session)
    assert await repo.count_for_disease(did, 0.3) == 2
    assert await repo.count_for_disease(did, 0.95) == 0
