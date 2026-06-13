"""Integration: the create -> engine path per entry mode, on real Postgres.

Proves the entry-modes wiring end-to-end against a testcontainer DB: the service ``create`` stamps
``input_modes`` + the run cursor, pre-fills the user-provided entity stages (S1 compounds / S3
targets / S4 disease targets) carrying their REAL gene symbols, and the engine SKIPS the frozen
(user-provided / not-applicable) stages on run while computing only the ``computed`` ones.

Stages 3/6/8 external clients are mocked (class-monkeypatch on the stage modules, mirroring
``test_run_to_stage6`` / ``test_run_to_stage8``). The overlap is REAL: the manual S3 targets and the
manual / seeded S4 disease targets are the SAME canonical ``target_id`` rows, so Stage 5's
``target_id`` intersection is genuinely non-empty and the gene symbols ride through to STRING /
g:Profiler — the linchpin guard for the Chunk-6-class "empty background" break.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.chembl import ChemblHit
from app.integrations.gprofiler import EnrichedTerm
from app.integrations.string_db import StringEdge
from app.integrations.uniprot import UniProtReason, UniProtRecord, UniProtResolution
from app.pipeline.stages import stage3, stage6, stage8

SETTLED = frozenset(
    {
        "complete",
        "failed",
        "stage_1_awaiting_approval",
        "stage_2_awaiting_approval",
        "stage_3_awaiting_approval",
        "stage_4_awaiting_approval",
        "stage_5_awaiting_approval",
        "stage_6_awaiting_approval",
        "stage_7_awaiting_approval",
        "stage_8_awaiting_approval",
    }
)


# ---------------------------------------------------------------------------
# Fakes — mirror test_run_to_stage6 / test_run_to_stage8.
# ---------------------------------------------------------------------------
class _FakeChembl:
    """ChEMBL returns TP53 + EGFR for any compound with an inchi_key (manual_compounds path)."""

    async def targets_for_inchikey(self, ik, *, min_pchembl, min_confidence):
        if not ik:
            return []
        return [ChemblHit("P04637", 6.5, "IC50"), ChemblHit("P00533", 6.5, "IC50")]


class _FakePubchem:
    async def active_targets_for_inchikey(self, ik):
        return []


class _FakeUniProt:
    async def resolve(self, acc):
        if acc == "P04637":
            return UniProtResolution(UniProtRecord("P04637", "TP53", "p53"), None)
        if acc == "P00533":
            return UniProtResolution(UniProtRecord("P00533", "EGFR", "egfr"), None)
        return UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)


class _FakeString:
    def __init__(self, edges=None):
        self._edges = edges or []

    async def network(self, gene_symbols, *, min_confidence, network_type):
        return list(self._edges)


class _FakeGprofiler:
    def __init__(self, terms=None):
        self._terms = terms or []

    async def profile(self, *, query, background, sources, correction, user_threshold):
        return list(self._terms)


_KEGG_TERM = EnrichedTerm(
    source="KEGG",
    native="KEGG:04151",
    name="PI3K-Akt signaling pathway",
    p_value=1e-5,
    term_size=354,
    query_size=2,
    intersection_size=2,
    intersection=["TP53", "EGFR"],
    significant=True,
)


def _patch(monkeypatch, *, string_edges=None, terms=None):
    monkeypatch.setattr(stage3, "ChemblClient", lambda http: _FakeChembl())
    monkeypatch.setattr(stage3, "PubChemBioAssayClient", lambda http: _FakePubchem())
    monkeypatch.setattr(stage3, "UniProtClient", lambda http: _FakeUniProt())
    monkeypatch.setattr(stage6, "StringClient", lambda http: _FakeString(string_edges))
    monkeypatch.setattr(stage8, "GprofilerClient", lambda http: _FakeGprofiler(terms))


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------
async def _seed_source_systems(s):
    await s.execute(
        text(
            "insert into source_systems(source_name, source_type) values "
            "('ChEMBL','api'),('PubChem BioAssay','api'),('UniProt','api') "
            "on conflict (source_name) do nothing"
        )
    )


async def _set_inchikeys(s, c1, c2):
    await s.execute(
        text("update compounds set inchi_key='IKX' where compound_id in (:c1,:c2)"),
        {"c1": c1, "c2": c2},
    )


async def _insert_target(s, *, acc, gene):
    """A canonical target keyed exactly as ``resolve_target_accession`` keys it (uniprot:<ACC>)."""
    tid = uuid.uuid4()
    await s.execute(
        text(
            "insert into targets(target_id, canonical_key, gene_symbol, uniprot_accession, "
            "source_url) values (:t,:k,:g,:a,:u)"
        ),
        {
            "t": tid,
            "k": f"uniprot:{acc}",
            "g": gene,
            "a": acc,
            "u": f"https://www.uniprot.org/uniprotkb/{acc}/entry",
        },
    )
    return tid


async def _insert_disease_target(s, *, disease_id, target_id, score):
    await s.execute(
        text(
            "insert into disease_targets(disease_target_id, disease_id, target_id, "
            "association_type, opentargets_score) values (:i,:d,:t,'overall',:s)"
        ),
        {"i": uuid.uuid4(), "d": disease_id, "t": target_id, "s": score},
    )


async def _poll(c, run_id, *, until=None, max_iters=120):
    final = {}
    for _ in range(max_iters):
        final = (await c.get(f"/analyses/{run_id}")).json()
        st = final.get("status")
        if until is not None and st == until:
            break
        if until is None and st in SETTLED:
            break
    return final


# ===========================================================================
# manual_compounds (auto): no plant, S1 user_provided, S2 ADME runs, reach S8.
# ===========================================================================
@pytest.mark.asyncio
async def test_manual_compounds_auto_runs_adme_then_completes(client, engine, monkeypatch):
    c, ids = client
    _patch(monkeypatch, string_edges=[StringEdge("TP53", "EGFR", 0.9)], terms=[_KEGG_TERM])

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed_source_systems(s)
        await _set_inchikeys(s, ids["c1"], ids["c2"])
        t_tp53 = await _insert_target(s, acc="P04637", gene="TP53")
        t_egfr = await _insert_target(s, acc="P00533", gene="EGFR")
        await _insert_disease_target(s, disease_id=ids["disease"], target_id=t_tp53, score=0.8)
        await _insert_disease_target(s, disease_id=ids["disease"], target_id=t_egfr, score=0.7)
        await s.commit()

    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_compounds",
            "disease_input_mode": "selection",
            "manual_compound_ids": [str(ids["c1"]), str(ids["c2"])],
            "disease_id": str(ids["disease"]),
            "plant_label": "custom extract",
            "mode": "auto",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    state = await _poll(c, run_id)
    assert state["status"] == "complete"
    assert state["parameters"]["input_modes"] == {
        "plant": "manual_compounds",
        "disease": "selection",
    }
    assert state["parameters"]["labels"]["plant"] == "custom extract"

    # S1 is the user-provided compound set; S2 ADME ran on it (both pass, 0 violations).
    s1 = state["stage_results"]["1"]
    assert s1["state"] == "user_provided"
    assert s1["count"] == 2
    assert state["stage_results"]["2"]["state"] == "computed"
    assert state["stage_results"]["2"]["count"] == 2

    # The whole computed tail ran through to the terminal stage.
    assert state["stage_results"]["8"]["state"] == "computed"
    assert state["stage_results"]["8"]["count"] == 1

    # No plant-catalog row was fabricated for the manual extract (manual_compounds has no plant).
    async with maker() as s:
        plant_n = (await s.execute(text("select count(*) from plants"))).scalar()
    # Only the two fixture plants exist; no third "custom extract" plant row.
    assert plant_n == 2


# ===========================================================================
# manual_targets + selection (guided): S1/S2 not_applicable, S3 user_provided,
# first checkpoint is stage_4_awaiting_approval, S5 reads the S3 targets.
# ===========================================================================
@pytest.mark.asyncio
async def test_manual_targets_guided_first_checkpoint_is_stage4(client, engine, monkeypatch):
    c, ids = client
    _patch(monkeypatch, string_edges=[StringEdge("TP53", "EGFR", 0.9)], terms=[_KEGG_TERM])

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed_source_systems(s)
        t_tp53 = await _insert_target(s, acc="P04637", gene="TP53")
        t_egfr = await _insert_target(s, acc="P00533", gene="EGFR")
        # The disease's own targets overlap the manual S3 targets -> non-empty S5.
        await _insert_disease_target(s, disease_id=ids["disease"], target_id=t_tp53, score=0.8)
        await _insert_disease_target(s, disease_id=ids["disease"], target_id=t_egfr, score=0.7)
        await s.commit()

    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_targets",
            "disease_input_mode": "selection",
            "manual_target_ids": [str(t_tp53), str(t_egfr)],
            "disease_id": str(ids["disease"]),
            "mode": "guided",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    # The run cursor starts at the first computed stage (4): guided parks at S4, never S1-S3.
    state = await _poll(c, run_id, until="stage_4_awaiting_approval")
    assert state["status"] == "stage_4_awaiting_approval"
    assert state["current_stage"] == 4

    assert state["stage_results"]["1"]["state"] == "not_applicable"
    assert state["stage_results"]["2"]["state"] == "not_applicable"
    s3 = state["stage_results"]["3"]
    assert s3["state"] == "user_provided"
    assert s3["count"] == 2
    # The manual S3 targets carry their REAL gene symbols (the downstream STRING/g:Profiler hinge).
    s3_genes = sorted(t["gene_symbol"] for t in s3["targets"])
    assert s3_genes == ["EGFR", "TP53"]

    # Advance S4 -> S5: overlap reads the user-provided S3 targets against the disease targets.
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "stage_5_running"
    state = await _poll(c, run_id, until="stage_5_awaiting_approval")
    assert state["status"] == "stage_5_awaiting_approval"
    assert state["stage_results"]["5"]["count"] == 2
    overlap_genes = sorted(o["gene_symbol"] for o in state["stage_results"]["5"]["overlap"])
    assert overlap_genes == ["EGFR", "TP53"]


# ===========================================================================
# manual_targets + manual_disease_targets (auto): frozen {1,2,3,4}; engine
# computes from S5; gene symbols present end-to-end (Chunk-6-class guard).
# ===========================================================================
@pytest.mark.asyncio
async def test_both_sides_manual_auto_computes_from_stage5(client, engine, monkeypatch):
    c, ids = client
    _patch(monkeypatch, string_edges=[StringEdge("TP53", "EGFR", 0.9)], terms=[_KEGG_TERM])

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed_source_systems(s)
        t_tp53 = await _insert_target(s, acc="P04637", gene="TP53")
        t_egfr = await _insert_target(s, acc="P00533", gene="EGFR")
        await s.commit()

    # The SAME two targets on both sides -> a real 2-target overlap from purely user-provided input.
    both = [str(t_tp53), str(t_egfr)]
    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_targets",
            "disease_input_mode": "manual_disease_targets",
            "manual_target_ids": both,
            "manual_disease_target_ids": both,
            "disease_label": "Custom disease set",
            "mode": "auto",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    state = await _poll(c, run_id)
    assert state["status"] == "complete"

    # Frozen prefix {1,2,3,4} kept as pre-filled; the engine computed only 5-8.
    assert state["stage_results"]["1"]["state"] == "not_applicable"
    assert state["stage_results"]["2"]["state"] == "not_applicable"
    assert state["stage_results"]["3"]["state"] == "user_provided"
    assert state["stage_results"]["4"]["state"] == "user_provided"

    # S5 overlap is non-empty and carries gene symbols (both rode through the edit layer).
    s5 = state["stage_results"]["5"]
    assert s5["count"] == 2
    assert sorted(o["gene_symbol"] for o in s5["overlap"]) == ["EGFR", "TP53"]

    # S6 built a network and S7 ranked hubs with gene symbols (the end-to-end identity guard).
    assert state["stage_results"]["6"]["state"] == "computed"
    assert state["stage_results"]["6"]["node_count"] == 2
    s7 = state["stage_results"]["7"]
    assert s7["state"] == "computed"
    s7_genes = sorted(h["gene_symbol"] for h in s7["hubs"])
    assert s7_genes == ["EGFR", "TP53"]

    # S8 enrichment ran against a NON-empty custom background (the Chunk-6-class break guard).
    s8 = state["stage_results"]["8"]
    assert s8["state"] == "computed"
    assert s8["degraded"] is False
    assert s8["count"] == 1
    assert s8["background_gene_count"] == 2


# ===========================================================================
# selection + manual_disease_targets (auto): S4 user_provided, disease_id NULL,
# engine SKIPS S4 mid-run, disease_label stored.
# ===========================================================================
@pytest.mark.asyncio
async def test_selection_plant_manual_disease_skips_stage4(client, engine, monkeypatch):
    c, ids = client
    _patch(monkeypatch, string_edges=[StringEdge("TP53", "EGFR", 0.9)], terms=[_KEGG_TERM])

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed_source_systems(s)
        await _set_inchikeys(s, ids["c1"], ids["c2"])
        # S3 resolves the plant's compounds to TP53/EGFR; the SAME two are the manual disease set.
        t_tp53 = await _insert_target(s, acc="P04637", gene="TP53")
        t_egfr = await _insert_target(s, acc="P00533", gene="EGFR")
        await s.commit()

    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "selection",
            "disease_input_mode": "manual_disease_targets",
            "plant_ids": [str(ids["plant_full"])],
            "manual_disease_target_ids": [str(t_tp53), str(t_egfr)],
            "disease_label": "My target panel",
            "mode": "auto",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    state = await _poll(c, run_id)
    assert state["status"] == "complete"
    assert state["disease_id"] is None  # manual_disease_targets forbids a disease_id
    assert state["parameters"]["labels"]["disease"] == "My target panel"

    # S4 is the frozen user-provided stage; it carries gene symbols and was never recomputed.
    s4 = state["stage_results"]["4"]
    assert s4["state"] == "user_provided"
    # Gene symbols ride on the single enriched targets list (no disease_targets view; L-11).
    assert "disease_targets" not in s4
    s4_genes = sorted(t["gene_symbol"] for t in s4["targets"])
    assert s4_genes == ["EGFR", "TP53"]

    # The selection plant side (S1-S3) computed normally; the overlap is real.
    assert state["stage_results"]["1"]["state"] == "computed"
    assert state["stage_results"]["5"]["count"] == 2


# ===========================================================================
# Atomicity: all-invalid manual paste -> 422, no run row.
# ===========================================================================
@pytest.mark.asyncio
async def test_all_invalid_manual_targets_422_no_run(client, engine):
    c, ids = client
    bogus = [str(uuid.uuid4()), str(uuid.uuid4())]

    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_targets",
            "disease_input_mode": "selection",
            "manual_target_ids": bogus,
            "disease_id": str(ids["disease"]),
            "mode": "auto",
        },
    )
    assert resp.status_code == 422

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        n = (await s.execute(text("select count(*) from analysis_runs"))).scalar()
    assert n == 0


# ===========================================================================
# Cap: a manual_target_ids list over the target cap -> 422, nothing created.
# ===========================================================================
@pytest.mark.asyncio
async def test_manual_targets_over_cap_422_no_run(client, engine):
    c, ids = client
    # Target cap is 5000; 5001 ids trips the cap BEFORE any existence check (no DB rows needed).
    over = [str(uuid.uuid4()) for _ in range(5001)]

    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_targets",
            "disease_input_mode": "selection",
            "manual_target_ids": over,
            "disease_id": str(ids["disease"]),
            "mode": "auto",
        },
    )
    assert resp.status_code == 422

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        n = (await s.execute(text("select count(*) from analysis_runs"))).scalar()
    assert n == 0
