"""Integration: drive a guided run all the way to Stage 4, then exercise Redo / manual add / cap."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.chembl import ChemblHit
from app.integrations.uniprot import UniProtRecord
from app.pipeline import limits
from app.pipeline.stages import stage3

SETTLED = frozenset(
    {
        "complete",
        "failed",
        "stage_1_awaiting_approval",
        "stage_2_awaiting_approval",
        "stage_3_awaiting_approval",
        "stage_4_awaiting_approval",
    }
)


class _FakeChembl:
    async def targets_for_inchikey(self, ik, *, min_pchembl, min_confidence):
        return [ChemblHit("P04637", 6.5, "IC50")] if ik else []


class _FakePubchem:
    async def active_targets_for_inchikey(self, ik):
        return []


class _FakeUniProt:
    async def resolve(self, acc):
        return UniProtRecord(acc, "TP53", "p53") if acc == "P04637" else None


async def _poll(c, run_id, *, until=None, max_iters=80):
    final = {}
    for _ in range(max_iters):
        final = (await c.get(f"/analyses/{run_id}")).json()
        st = final.get("status")
        if until is not None and st == until:
            break
        if until is None and st in SETTLED:
            break
    return final


@pytest.mark.asyncio
async def test_guided_run_reaches_stage4_with_scores(client, engine, monkeypatch):
    c, ids = client
    monkeypatch.setattr(stage3, "ChemblClient", lambda http: _FakeChembl())
    monkeypatch.setattr(stage3, "PubChemBioAssayClient", lambda http: _FakePubchem())
    monkeypatch.setattr(stage3, "UniProtClient", lambda http: _FakeUniProt())

    maker = async_sessionmaker(engine, expire_on_commit=False)
    seeded_target_id = uuid.uuid4()
    async with maker() as s:
        await s.execute(
            text(
                "insert into source_systems(source_name, source_type) values "
                "('ChEMBL','api'),('PubChem BioAssay','api'),('UniProt','api') "
                "on conflict (source_name) do nothing"
            )
        )
        await s.execute(
            text("update compounds set inchi_key='IKX' where compound_id in (:c1,:c2)"),
            {"c1": ids["c1"], "c2": ids["c2"]},
        )
        # Two seeded disease-targets for the run's disease (scores 0.8 and 0.2).
        await s.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol, uniprot_accession, "
                "source_url) values (:t,'uniprot:P55555','GENEZ','P55555',"
                "'https://www.uniprot.org/uniprotkb/P55555/entry')"
            ),
            {"t": seeded_target_id},
        )
        await s.execute(
            text(
                "insert into disease_targets(disease_target_id, disease_id, target_id, "
                "association_type, score) values (:i,:d,:t,'overall',0.8)"
            ),
            {"i": uuid.uuid4(), "d": ids["disease"], "t": seeded_target_id},
        )
        low_t = uuid.uuid4()
        await s.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol, uniprot_accession) "
                "values (:t,'uniprot:P66666','GENElow','P66666')"
            ),
            {"t": low_t},
        )
        await s.execute(
            text(
                "insert into disease_targets(disease_target_id, disease_id, target_id, "
                "association_type, score) values (:i,:d,:t,'overall',0.2)"
            ),
            {"i": uuid.uuid4(), "d": ids["disease"], "t": low_t},
        )
        await s.commit()

    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_full"])],
            "disease_id": str(ids["disease"]),
            "mode": "guided",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]
    assert resp.json()["parameters"]["disease_targets"] == {"min_score": 0.3}

    await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "stage_2_running"
    await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "stage_3_running"
    await _poll(c, run_id, until="stage_3_awaiting_approval")
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "stage_4_running"
    state = await _poll(c, run_id, until="stage_4_awaiting_approval")
    assert state["status"] == "stage_4_awaiting_approval", "guided run must checkpoint at S4"

    s4 = state["stage_results"]["4"]
    # min_score 0.3 keeps the 0.8 target, drops the 0.2 one.
    assert s4["count"] == 1
    assert s4["min_score_applied"] == 0.3
    assert [d["gene_symbol"] for d in s4["disease_targets"]] == ["GENEZ"]
    assert s4["disease_targets"][0]["score"] == 0.8

    # --- min_score Redo re-filters (reset-from/4 re-runs S4 only) ---
    reset = await c.post(
        f"/analyses/{run_id}/reset-from/4",
        json={"parameters": {"4": {"min_score": 0.1}}},
    )
    assert reset.status_code == 202
    assert reset.json()["status"] == "stage_4_running"
    state = await _poll(c, run_id, until="stage_4_awaiting_approval")
    s4 = state["stage_results"]["4"]
    assert s4["count"] == 2  # 0.2 target now included
    assert state["parameters"]["disease_targets"]["min_score"] == 0.1
    assert not any(k in state["stage_results"] for k in ("5", "6", "7", "8"))

    # --- manual disease-target add: run-set grows, NO disease_targets edge, target persisted ---
    before = None
    async with maker() as s:
        before = (await s.execute(text("select count(*) from disease_targets"))).scalar_one()
    manual_t = uuid.uuid4()
    async with maker() as s:
        await s.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol, uniprot_accession) "
                "values (:t,'uniprot:P77777','MANUALG','P77777')"
            ),
            {"t": manual_t},
        )
        await s.commit()
    edit = await c.post(
        f"/analyses/{run_id}/stages/4/edit",
        json={"add": [str(manual_t)], "remove": []},
    )
    assert edit.status_code == 202
    state = await _poll(c, run_id)
    tags = {t["target_id"]: t["tag"] for t in state["stage_results"]["4"]["targets"]}
    assert tags.get(str(manual_t)) == "user-added"
    async with maker() as s:
        after = (await s.execute(text("select count(*) from disease_targets"))).scalar_one()
    assert after == before, "manual disease-target add must NOT write a disease_targets edge"

    # --- cap: shrink the target cap and prove an overflow add is 422 (nothing truncated) ---
    monkeypatch.setattr(limits.contracts, "max_targets", lambda: 2)
    extra = uuid.uuid4()
    async with maker() as s:
        await s.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol) "
                "values (:t,'uniprot:P88888','OVER')"
            ),
            {"t": extra},
        )
        await s.commit()
    over = await c.post(
        f"/analyses/{run_id}/stages/4/edit",
        json={"add": [str(extra)], "remove": []},
    )
    assert over.status_code == 422
