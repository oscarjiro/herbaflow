"""Integration coverage for the C-T-P graph JSON endpoint (real PG)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


def _stage_results(cid: str, tid: str) -> dict:
    """A complete-run stage_results with a Stage-3 edge into the Stage-5 overlap plus a
    Stage-8 term whose intersection covers the overlap gene (so both edge kinds appear)."""
    return {
        "3": {
            "compound_targets": [
                {
                    "compound_id": cid,
                    "target_id": tid,
                    "prediction_method": "chembl_bioactivity",
                    "gene_symbol": "PPARG",
                }
            ],
            "count": 1,
        },
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
        },
        "7": {"hubs": [{"rank": 1, "target_id": tid, "gene_symbol": "PPARG"}], "count": 1},
        "8": {
            "terms": [
                {
                    "source": "KEGG",
                    "term_id": "KEGG:04151",
                    "name": "PI3K-Akt",
                    "p_value": 1.2e-4,
                    "intersection": ["PPARG"],
                }
            ],
            "count": 1,
        },
    }


async def _seed_entities(maker) -> tuple[str, str]:
    cid = uuid.uuid4()
    tid = uuid.uuid4()
    async with maker() as s:
        await s.execute(
            text(
                "insert into compounds"
                "(compound_id, canonical_key, canonical_name, inchi_key, smiles, "
                " validation_status) "
                "values (:c, 'inchikey:GRAPH', 'CURCUMIN', 'VFLDPWHFBUODDF-FCXRPNKRSA-N', "
                "'CC=O', 'externally_validated')"
            ),
            {"c": cid},
        )
        await s.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol, uniprot_accession) "
                "values (:t, 'uniprot:P37231', 'PPARG', 'P37231')"
            ),
            {"t": tid},
        )
        await s.commit()
    return str(cid), str(tid)


async def _seed_run(
    maker,
    *,
    status: str,
    with_results: bool,
    params: dict | None = None,
) -> uuid.UUID:
    cid, tid = await _seed_entities(maker)
    aid = uuid.uuid4()
    sr = _stage_results(cid, tid) if with_results else {}
    completed = datetime.now(UTC) if status == "complete" else None
    async with maker() as s:
        await s.execute(
            text(
                "insert into analysis_runs"
                "(analysis_id, analysis_name, status, mode, parameters, stage_results, "
                " created_at, completed_at, updated_at) "
                "values (:aid, 'Graph run', :status, 'guided', cast(:params as jsonb), "
                "cast(:sr as jsonb), now(), :completed, now())"
            ),
            {
                "aid": aid,
                "status": status,
                "params": json.dumps(params or {}),
                "sr": json.dumps(sr),
                "completed": completed,
            },
        )
        await s.commit()
    return aid


@pytest_asyncio.fixture()
async def seed_complete_run(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return await _seed_run(maker, status="complete", with_results=True)


@pytest_asyncio.fixture()
async def seed_incomplete_run(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return await _seed_run(maker, status="stage_8_awaiting_approval", with_results=True)


@pytest_asyncio.fixture()
async def seed_complete_target_only_run(engine):
    """A complete manual_targets run: no compounds, so the C-T-P graph is empty."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return await _seed_run(
        maker,
        status="complete",
        with_results=True,
        params={"input_modes": {"plant": "manual_targets", "disease": "selection"}},
    )


@pytest.mark.asyncio
async def test_complete_run_returns_graph(client, seed_complete_run):
    c, _ = client
    aid = seed_complete_run
    resp = await c.get(f"/analyses/{aid}/ctp-graph")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "content-disposition" not in resp.headers
    graph = resp.json()
    types = {n["type"] for n in graph["nodes"]}
    assert {"compound", "target", "pathway"} <= types
    interactions = {e["interaction"] for e in graph["edges"]}
    assert {"compound-target", "target-pathway"} <= interactions
    # the overlap target carries its accession + hub flag through to the node
    target_node = next(n for n in graph["nodes"] if n["type"] == "target")
    assert target_node["uniprot_accession"] == "P37231"
    assert target_node["is_hub"] == "true"


@pytest.mark.asyncio
async def test_incomplete_run_409(client, seed_incomplete_run):
    c, _ = client
    aid = seed_incomplete_run
    resp = await c.get(f"/analyses/{aid}/ctp-graph")
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_unknown_run_404(client):
    c, _ = client
    resp = await c.get(f"/analyses/{uuid.uuid4()}/ctp-graph")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_target_only_run_empty_graph(client, seed_complete_target_only_run):
    c, _ = client
    aid = seed_complete_target_only_run
    resp = await c.get(f"/analyses/{aid}/ctp-graph")
    assert resp.status_code == 200
    assert resp.json() == {"nodes": [], "edges": []}
