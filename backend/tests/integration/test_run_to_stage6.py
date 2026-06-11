"""Integration: drive a run through Stage 5 (overlap) and Stage 6 (PPI) on real Postgres.

STRING is mocked (class-monkeypatch on the stage module, mirroring the Stage-3 fakes); the
overlap is REAL — Stage 3 resolves the mocked ChEMBL accessions to pre-seeded canonical targets
(``resolve_target_accession`` DB-hits ``canonical_key='uniprot:<ACC>'``), and those same target_ids
are the run's disease_targets, so Stage 5's ``target_id`` intersection is genuinely non-empty.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.chembl import ChemblHit
from app.integrations.string_db import StringEdge
from app.integrations.uniprot import UniProtReason, UniProtRecord, UniProtResolution
from app.pipeline.stages import stage3, stage6

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
    }
)


# --- Stage-3 fakes: two compound-targets that resolve to the pre-seeded canonical targets. ---
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
    def __init__(self, edges=None, *, fail=False):
        self._edges = edges or []
        self._fail = fail

    async def network(self, gene_symbols, *, min_confidence, network_type):
        if self._fail:
            from app.errors import ServiceUnavailableError

            raise ServiceUnavailableError(detail="STRING is unavailable.")
        return list(self._edges)


def _patch_stage_clients(monkeypatch, string_fake):
    monkeypatch.setattr(stage3, "ChemblClient", lambda http: _FakeChembl())
    monkeypatch.setattr(stage3, "PubChemBioAssayClient", lambda http: _FakePubchem())
    monkeypatch.setattr(stage3, "UniProtClient", lambda http: _FakeUniProt())
    monkeypatch.setattr(stage6, "StringClient", lambda http: string_fake)


async def _seed_source_systems(s, c1, c2):
    await s.execute(
        text(
            "insert into source_systems(source_name, source_type) values "
            "('ChEMBL','api'),('PubChem BioAssay','api'),('UniProt','api') "
            "on conflict (source_name) do nothing"
        )
    )
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
            "association_type, score) values (:i,:d,:t,'overall',:s)"
        ),
        {"i": uuid.uuid4(), "d": disease_id, "t": target_id, "s": score},
    )


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


async def _drive_to_stage4(c, run_id):
    """Advance a guided run S1->S2->S3->S4, parking at each checkpoint."""
    await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "stage_2_running"
    await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "stage_3_running"
    await _poll(c, run_id, until="stage_3_awaiting_approval")
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "stage_4_running"
    state = await _poll(c, run_id, until="stage_4_awaiting_approval")
    assert state["status"] == "stage_4_awaiting_approval"


@pytest.mark.asyncio
async def test_guided_run_reaches_stage5_then_stage6(client, engine, monkeypatch):
    """Guided: real 2-target overlap parks at S5 (hypergeom/jaccard) then S6 (1 edge, 2 nodes)."""
    c, ids = client
    _patch_stage_clients(monkeypatch, _FakeString([StringEdge("TP53", "EGFR", 0.9)]))

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed_source_systems(s, ids["c1"], ids["c2"])
        t_tp53 = await _insert_target(s, acc="P04637", gene="TP53")
        t_egfr = await _insert_target(s, acc="P00533", gene="EGFR")
        await _insert_disease_target(s, disease_id=ids["disease"], target_id=t_tp53, score=0.8)
        await _insert_disease_target(s, disease_id=ids["disease"], target_id=t_egfr, score=0.7)
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

    await _drive_to_stage4(c, run_id)

    # Advance S4 -> S5: parks at the S5 checkpoint with a real 2-target overlap.
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "stage_5_running"
    state = await _poll(c, run_id, until="stage_5_awaiting_approval")
    assert state["status"] == "stage_5_awaiting_approval"
    s5 = state["stage_results"]["5"]
    assert s5["count"] >= 1
    assert s5["count"] == 2  # both TP53 and EGFR are shared
    assert "hypergeometric" in s5 and s5["hypergeometric"]["k"] == 2
    assert "jaccard" in s5
    overlap_genes = sorted(o["gene_symbol"] for o in s5["overlap"])
    assert overlap_genes == ["EGFR", "TP53"]

    # Advance S5 -> S6: parks at the S6 checkpoint with the mocked STRING edge.
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "stage_6_running"
    state = await _poll(c, run_id, until="stage_6_awaiting_approval")
    assert state["status"] == "stage_6_awaiting_approval"
    s6 = state["stage_results"]["6"]
    assert s6["state"] == "computed"
    assert s6["node_count"] == 2
    assert s6["edge_count"] == 1

    # Final advance: S6 is the last runnable stage -> run completes (optional tail check).
    assert (await c.post(f"/analyses/{run_id}/advance")).json()["status"] == "complete"


@pytest.mark.asyncio
async def test_zero_overlap_auto_fails(client, engine, monkeypatch):
    """Auto: S3 -> TP53 but the only disease_target is a different protein -> 0 overlap -> fail."""
    c, ids = client
    _patch_stage_clients(monkeypatch, _FakeString([]))

    # ChEMBL returns only P04637 (TP53) for this scenario.
    async def _only_tp53(self, ik, *, min_pchembl, min_confidence):
        return [ChemblHit("P04637", 6.5, "IC50")] if ik else []

    monkeypatch.setattr(_FakeChembl, "targets_for_inchikey", _only_tp53)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed_source_systems(s, ids["c1"], ids["c2"])
        # Pre-seed TP53 so S3 resolves it, but DO NOT make it a disease_target.
        await _insert_target(s, acc="P04637", gene="TP53")
        # The disease's only target is a DIFFERENT, non-overlapping protein.
        t_other = await _insert_target(s, acc="P99999", gene="OTHER")
        await _insert_disease_target(s, disease_id=ids["disease"], target_id=t_other, score=0.8)
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

    state = await _poll(c, run_id)  # auto chains; settles at failed
    assert state["status"] == "failed"
    s5 = state["stage_results"]["5"]
    assert s5["count"] == 0
    assert "shared targets" in (state.get("error_message") or "").lower()


@pytest.mark.asyncio
async def test_overlap_cap_blocks_then_recovers_on_redo(client, engine, monkeypatch):
    """Auto: a >cap overlap with opt-in off BLOCKS (auto fail); enabling top-N recovers.

    NOTE on the cap value: the ppi contract hard floor is ``max_proteins >= 50`` (the engine's
    ``_validate_overrides`` 422s anything below it), so ``max_proteins=1`` from the task sketch is
    not a legal override. The block is forced with a REAL 60-target overlap and ``max_proteins=50``
    instead — still a genuine overflow (60 > 50), not a stubbed one.
    """
    c, ids = client
    n = 60
    accs = [f"P1{i:04d}" for i in range(n)]  # P10000..P10059, valid UniProtKB grammar
    genes = [f"G{i:04d}" for i in range(n)]

    # ChEMBL returns all 60 accessions; UniProt resolves each to its gene (matches pre-seed).
    async def _all_accs(self, ik, *, min_pchembl, min_confidence):
        return [ChemblHit(a, 6.5, "IC50") for a in accs] if ik else []

    async def _resolve_all(self, acc):
        try:
            i = accs.index(acc)
        except ValueError:
            return UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)
        return UniProtResolution(UniProtRecord(acc, genes[i], genes[i].lower()), None)

    monkeypatch.setattr(_FakeChembl, "targets_for_inchikey", _all_accs)
    monkeypatch.setattr(_FakeUniProt, "resolve", _resolve_all)
    # Every overlap gene is its own STRING edge endpoint; give a couple of edges to exercise build.
    string_fake = _FakeString([StringEdge(genes[0], genes[1], 0.9)])
    _patch_stage_clients(monkeypatch, string_fake)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed_source_systems(s, ids["c1"], ids["c2"])
        for i, (acc, gene) in enumerate(zip(accs, genes, strict=True)):
            tid = await _insert_target(s, acc=acc, gene=gene)
            # Descending score so the top-N cap is deterministic.
            await _insert_disease_target(
                s, disease_id=ids["disease"], target_id=tid, score=round(0.9 - i * 0.001, 4)
            )
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

    # Auto run with the default cap (2000) computes S6 over all 60 nodes -> complete.
    state = await _poll(c, run_id)
    assert state["status"] == "complete"
    assert state["stage_results"]["5"]["count"] == n
    assert state["stage_results"]["6"]["state"] == "computed"
    assert state["stage_results"]["6"]["node_count"] == n

    # Redo S6 with a cap of 50 and opt-in OFF: 60 > 50 -> blocked -> AUTO fail.
    reset = await c.post(
        f"/analyses/{run_id}/reset-from/6",
        json={"parameters": {"6": {"max_proteins": 50}}},
    )
    assert reset.status_code == 202
    state = await _poll(c, run_id)
    assert state["status"] == "failed"
    msg = (state.get("error_message") or "").lower()
    assert "exceeds" in msg or "ceiling" in msg
    assert state["stage_results"]["6"]["blocked"] is True
    assert state["stage_results"]["6"]["overlap_count"] == n

    # Redo S6 enabling the top-N cap (max_proteins stays 50 from the merged group) -> top-50.
    reset = await c.post(
        f"/analyses/{run_id}/reset-from/6",
        json={"parameters": {"6": {"allow_top_n_cap": True}}},
    )
    assert reset.status_code == 202
    state = await _poll(c, run_id)
    assert state["status"] == "complete"
    s6 = state["stage_results"]["6"]
    assert s6["state"] == "computed"
    assert s6["node_count"] == 50
    assert s6["capped"]["applied"] is True


@pytest.mark.asyncio
async def test_string_outage_fails_run(client, engine, monkeypatch):
    """Auto: real 2-target overlap, but STRING raises ServiceUnavailableError -> run fails."""
    c, ids = client
    _patch_stage_clients(monkeypatch, _FakeString(fail=True))

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await _seed_source_systems(s, ids["c1"], ids["c2"])
        t_tp53 = await _insert_target(s, acc="P04637", gene="TP53")
        t_egfr = await _insert_target(s, acc="P00533", gene="EGFR")
        await _insert_disease_target(s, disease_id=ids["disease"], target_id=t_tp53, score=0.8)
        await _insert_disease_target(s, disease_id=ids["disease"], target_id=t_egfr, score=0.7)
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
    assert state["status"] == "failed"
    # The overlap WAS real (S5 computed 2) before STRING took the run down at S6.
    assert state["stage_results"]["5"]["count"] == 2
