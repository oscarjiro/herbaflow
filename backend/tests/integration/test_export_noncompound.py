"""Integration coverage for compound-free (target-only) run exports.

A ``manual_targets`` plant side introduces no compounds, so the compound-target-pathway
and docking artifacts are not applicable. The export endpoints that build those artifacts
directly (the network-and-docking bundle and the CTP/docking CSVs) must 404, while the
compound-independent PPI/stage outputs stay available.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


def _stage_results(tid: str) -> dict:
    """A manual-targets run: NO Stage-3 compound_targets, but a Stage-5 overlap and a
    Stage-7 hub so the compound-independent PPI/stage CSVs still build a valid 200."""
    return {
        "5": {
            "overlap": [
                {
                    "target_id": tid,
                    "gene_symbol": "PPARG",
                    "uniprot_accession": "P37231",
                    "opentargets_score": 0.8,
                }
            ],
            "count": 1,
            "compound_target_count": 0,
            "disease_target_count": 911,
        },
        "7": {"hubs": [{"rank": 1, "target_id": tid, "gene_symbol": "PPARG"}], "count": 1},
    }


async def _seed_target(maker) -> str:
    tid = uuid.uuid4()
    async with maker() as s:
        await s.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol, uniprot_accession) "
                "values (:t, 'uniprot:P37231', 'PPARG', 'P37231')"
            ),
            {"t": tid},
        )
        await s.commit()
    return str(tid)


@pytest_asyncio.fixture()
async def seed_noncompound_run(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    tid = await _seed_target(maker)
    aid = uuid.uuid4()
    params = {"input_modes": {"plant": "manual_targets", "disease": "manual_disease_targets"}}
    async with maker() as s:
        await s.execute(
            text(
                "insert into analysis_runs"
                "(analysis_id, analysis_name, status, mode, parameters, stage_results, "
                " created_at, completed_at, updated_at) "
                "values (:aid, 'Target-only run', 'complete', 'guided', "
                "cast(:params as jsonb), cast(:sr as jsonb), now(), :completed, now())"
            ),
            {
                "aid": aid,
                "params": json.dumps(params),
                "sr": json.dumps(_stage_results(tid)),
                "completed": datetime.now(UTC),
            },
        )
        await s.commit()
    return aid


@pytest.mark.asyncio
async def test_noncompound_export_drops_ctp_and_docking(client, seed_noncompound_run):
    c, _ = client
    aid = seed_noncompound_run
    assert (await c.get(f"/analyses/{aid}/export/network-and-docking.zip")).status_code == 404
    assert (await c.get(f"/analyses/{aid}/export/ctp-nodes.csv")).status_code == 404
    assert (await c.get(f"/analyses/{aid}/export/ctp-edges.csv")).status_code == 404
    assert (await c.get(f"/analyses/{aid}/export/docking.csv")).status_code == 404
    # PPI stays available:
    assert (await c.get(f"/analyses/{aid}/export/stage6_ppi_nodes.csv")).status_code == 200
    assert (await c.get(f"/analyses/{aid}/export/stages.zip")).status_code == 200
    # generalized route also 404s the CTP png:
    assert (await c.get(f"/analyses/{aid}/export/ctp-network.png")).status_code == 404
