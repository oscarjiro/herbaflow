"""Integration coverage for the results-handoff export endpoints (real PG)."""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


def _stage_results(cid: str, tid: str) -> dict:
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
                "values (:c, 'inchikey:EXP', 'CURCUMIN', 'VFLDPWHFBUODDF-FCXRPNKRSA-N', "
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


async def _seed_run(maker, *, status: str, with_results: bool) -> uuid.UUID:
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
                "values (:aid, 'Export run', :status, 'guided', cast(:params as jsonb), "
                "cast(:sr as jsonb), now(), :completed, now())"
            ),
            {
                "aid": aid,
                "status": status,
                "params": json.dumps({}),
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


@pytest.mark.asyncio
async def test_complete_run_export_zip_has_four_files(client, seed_complete_run):
    c, _ = client
    aid = seed_complete_run
    resp = await c.get(f"/analyses/{aid}/export/all-results.zip")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = set(zf.namelist())
    assert {
        "README.txt",
        "report.md",
        "network-and-docking/ctp-nodes.csv",
        "stages/stage5_overlap.csv",
    } <= names


@pytest.mark.asyncio
async def test_incomplete_run_export_409(client, seed_incomplete_run):
    c, _ = client
    aid = seed_incomplete_run
    resp = await c.get(f"/analyses/{aid}/export/all-results.zip")
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_per_artifact_content_types(client, seed_complete_run):
    c, _ = client
    aid = seed_complete_run
    nodes = await c.get(f"/analyses/{aid}/export/ctp-nodes.csv")
    assert nodes.headers["content-type"].startswith("text/csv")
    report = await c.get(f"/analyses/{aid}/export/report.md")
    assert report.headers["content-type"].startswith("text/markdown")


@pytest.mark.asyncio
async def test_docking_csv_has_hub_compound_row(client, seed_complete_run):
    c, _ = client
    aid = seed_complete_run
    resp = await c.get(f"/analyses/{aid}/export/docking.csv")
    assert resp.status_code == 200
    body = resp.text
    assert "PPARG" in body and "P37231" in body and "CURCUMIN" in body


@pytest.mark.asyncio
async def test_unknown_run_404(client):
    c, _ = client
    resp = await c.get(f"/analyses/{uuid.uuid4()}/export/all-results.zip")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bundle_endpoints(client, seed_complete_run):
    c, _ = client
    aid = seed_complete_run
    cases = [
        ("report.md", "text/markdown"),
        ("network-and-docking.zip", "application/zip"),
        ("stages.zip", "application/zip"),
        ("all-results.zip", "application/zip"),
    ]
    for name, expected_type in cases:
        resp = await c.get(f"/analyses/{aid}/export/{name}")
        assert resp.status_code == 200, name
        assert expected_type in resp.headers["content-type"], name
        assert "filename=" in resp.headers["content-disposition"], name


@pytest.mark.asyncio
async def test_assemble_export_shape(engine, seed_complete_run):
    from app.services.export import assemble_export

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        art = await assemble_export(session, seed_complete_run)
    assert art.report.startswith("#")
    assert art.stage_csvs[5].splitlines()[0] == "gene_symbol,uniprot_accession,opentargets_score"
    assert art.ppi_edges.splitlines()[0] == "source,target,confidence"
    with zipfile.ZipFile(io.BytesIO(art.network_bundle())) as zf:
        assert "ctp-nodes.csv" in zf.namelist()


@pytest.mark.asyncio
async def test_stage_csv_endpoint(client, seed_complete_run):
    c, _ = client
    aid = seed_complete_run
    resp = await c.get(f"/analyses/{aid}/export/stage5_overlap.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "gene_symbol" in resp.text
