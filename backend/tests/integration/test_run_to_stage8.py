"""Integration: drive a run through Stage 7 (hubs) and Stage 8 (enrichment) on real Postgres.

STRING and g:Profiler are mocked (class-monkeypatch on the stage modules, mirroring stage 3/6);
the overlap is REAL (Stage 3 resolves mocked ChEMBL accessions to pre-seeded canonical targets
that are also the disease_targets). Proves: S7 ranks hubs from the S6 network; S8 enriches the
overlap against the S3 universe; a g:Profiler outage DEGRADES (run still completes, EN-5);
approving S8 completes the run with completed_at set; a Redo of S7 does NOT re-run S8
(S8 depends on S5 not S7 — DAG-1 proof).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.chembl import ChemblHit
from app.integrations.gprofiler import EnrichedTerm, GprofilerError
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
# Fakes — mirror test_run_to_stage6 for stages 3/6; add g:Profiler for stage 8.
# ---------------------------------------------------------------------------


class _FakeChembl:
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
    def __init__(self, terms=None, *, fail=False):
        self._terms = terms or []
        self._fail = fail

    async def profile(
        self, *, query, background, sources, correction, user_threshold, no_iea=False
    ):
        if self._fail:
            raise GprofilerError("service down")
        return list(self._terms)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch(monkeypatch, *, string_edges, gprofiler):
    monkeypatch.setattr(stage3, "ChemblClient", lambda http: _FakeChembl())
    monkeypatch.setattr(stage3, "PubChemBioAssayClient", lambda http: _FakePubchem())
    monkeypatch.setattr(stage3, "UniProtClient", lambda http: _FakeUniProt())
    monkeypatch.setattr(stage6, "StringClient", lambda http: _FakeString(string_edges))
    monkeypatch.setattr(stage8, "GprofilerClient", lambda http: gprofiler)


async def _seed(s, ids):
    """Seed source systems, inchi_key on compounds, canonical targets + disease links."""
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
    tids = {}
    for acc, gene in (("P04637", "TP53"), ("P00533", "EGFR")):
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
        tids[gene] = tid
    for gene, score in (("TP53", 0.8), ("EGFR", 0.7)):
        await s.execute(
            text(
                "insert into disease_targets(disease_target_id, disease_id, target_id, "
                "association_type, opentargets_score) values (:i,:d,:t,'overall',:s)"
            ),
            {"i": uuid.uuid4(), "d": ids["disease"], "t": tids[gene], "s": score},
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_run_completes_through_stage8(client, engine, monkeypatch):
    """Auto: real 2-target overlap -> S6 (1 edge) -> S7 hubs -> S8 enrichment -> complete."""
    c, ids = client
    term = EnrichedTerm(
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
    _patch(
        monkeypatch,
        string_edges=[StringEdge("TP53", "EGFR", 0.9)],
        gprofiler=_FakeGprofiler([term]),
    )

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed(s, ids)
        await s.commit()

    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_full"])],
            "disease_id": str(ids["disease"]),
            "mode": "auto",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    state = await _poll(c, run_id)
    assert state["status"] == "complete"
    assert state.get("completed_at") is not None

    s7 = state["stage_results"]["7"]
    assert s7["state"] == "computed"
    assert s7["count"] == 2  # both TP53 and EGFR ranked as hubs

    s8 = state["stage_results"]["8"]
    assert s8["state"] == "computed"
    assert s8["count"] == 1
    assert s8["terms"][0]["term_id"] == "KEGG:04151"
    assert s8["background_source"] == "compound_target_universe"
    # The Stage-3 universe gene symbols must survive the edit layer into the custom background
    # (regression guard: an empty background silently degraded Stage 8 against the live API).
    assert s8["background_gene_count"] == 2
    assert s8["input_gene_count"] == 2
    assert s8["degraded"] is False


@pytest.mark.asyncio
async def test_gprofiler_outage_degrades_but_completes(client, engine, monkeypatch):
    """Auto: g:Profiler outage -> Stage 8 degraded but run STILL completes (EN-5)."""
    c, ids = client
    _patch(
        monkeypatch,
        string_edges=[StringEdge("TP53", "EGFR", 0.9)],
        gprofiler=_FakeGprofiler(fail=True),
    )

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed(s, ids)
        await s.commit()

    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_full"])],
            "disease_id": str(ids["disease"]),
            "mode": "auto",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    state = await _poll(c, run_id)
    assert state["status"] == "complete"
    assert state.get("completed_at") is not None

    s8 = state["stage_results"]["8"]
    assert s8["degraded"] is True
    assert s8["count"] == 0
    assert "source_degraded" in s8["flags"]


@pytest.mark.asyncio
async def test_redo_stage7_does_not_rerun_stage8(client, engine, monkeypatch):
    """Redo of S7 re-runs only S7 — S8 (depends on S5, not S7) is untouched (DAG-1 proof)."""
    c, ids = client
    term = EnrichedTerm(
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
    _patch(
        monkeypatch,
        string_edges=[StringEdge("TP53", "EGFR", 0.9)],
        gprofiler=_FakeGprofiler([term]),
    )

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed(s, ids)
        await s.commit()

    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_full"])],
            "disease_id": str(ids["disease"]),
            "mode": "auto",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    state = await _poll(c, run_id)
    assert state["status"] == "complete"
    s8_before = state["stage_results"]["8"]
    s7_before_top_n = state["stage_results"]["7"]["top_n"]

    # Redo S7 with a different top_n: closure(7) = {} -> only S7 is re-run; S8 is untouched.
    reset = await c.post(
        f"/analyses/{run_id}/reset-from/7",
        json={"parameters": {"7": {"top_n": 1}}},
    )
    assert reset.status_code == 202

    state = await _poll(c, run_id)
    assert state["status"] == "complete"

    # S7 was re-run with a new top_n.
    assert state["stage_results"]["7"]["top_n"] == 1
    assert state["stage_results"]["7"]["top_n"] != s7_before_top_n

    # S8 result is identical — it was never cleared or recomputed.
    assert state["stage_results"]["8"] == s8_before
