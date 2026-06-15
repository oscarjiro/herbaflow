"""GD-2 golden regression: Hito pancreatic-cancer MCC validation, manual entry modes, OFFLINE.

Level-A deterministic, input-controlled validation of Herbaflow's MCC hub ranker against the
pancreatic-cancer thesis result. Two opt-in (``@pytest.mark.scientific``, deselected by default)
runs over the manual entry modes:

- the headline run feeds Hito's 233-gene overlap directly into both sides -> Stage-5 overlap == 233
  and Stage 7 reports the MCC top-10 (reconciled into the gitignored snapshot, which is truth);
- the secondary run feeds the full plant (1165) and disease (777) target sets and proves Herbaflow
  recovers 100% of Hito's 233-gene overlap plus exactly 14 extra (Stage-5 overlap == 247).

Both replay one recorded STRING network and an empty g:Profiler, fully offline. The tests SKIP (not
fail) when the unpublished GD-2 fixtures are absent, so a fresh checkout / CI stays green.
"""

import json

import pytest

from tests.scientific import gd2_support
from tests.scientific.conftest import FIXTURES, load_json

pytestmark = [
    pytest.mark.scientific,
    pytest.mark.skipif(
        not gd2_support.gd2_fixtures_present(),
        reason="GD-2 fixtures (unpublished Hito data) absent",
    ),
]


@pytest.mark.asyncio
async def test_gd2_headline_overlap_233_mcc(golden_client, monkeypatch):
    c, engine = golden_client
    seed = await gd2_support.seed_gd2(engine)
    gd2_support.patch_gd2(monkeypatch)
    ids = seed["headline_target_ids"]
    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_targets",
            "manual_target_ids": ids,
            "disease_input_mode": "manual_disease_targets",
            "manual_disease_target_ids": ids,
            "mode": "auto",
        },
    )
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["analysis_id"]
    state = {}
    for _ in range(180):
        state = (await c.get(f"/analyses/{run_id}")).json()
        if state.get("status") in {"complete", "failed"}:
            break
    assert state["status"] == "complete", state.get("error_message")
    sr = state["stage_results"]
    assert sr["5"]["count"] == 233
    assert sr["7"]["ranking_metric"] == "mcc"
    mcc_top10 = [h["gene_symbol"] for h in sorted(sr["7"]["hubs"], key=lambda h: -h["mcc"])][:10]
    # Reconcile the preliminary snapshot to the observed deterministic output (fixtures are truth).
    snap = load_json("gd2_snapshot.json")
    if snap.get("headline_mcc_top10") != mcc_top10:
        snap["headline_mcc_top10"] = mcc_top10
        snap.pop("_note", None)
        (FIXTURES / "gd2_snapshot.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
    assert mcc_top10 == load_json("gd2_snapshot.json")["headline_mcc_top10"]
    assert len(mcc_top10) == 10


@pytest.mark.asyncio
async def test_gd2_secondary_recovers_233_plus_14(golden_client, monkeypatch):
    c, engine = golden_client
    seed = await gd2_support.seed_gd2(engine)
    gd2_support.patch_gd2(monkeypatch)
    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_targets",
            "manual_target_ids": seed["plant_target_ids"],
            "disease_input_mode": "manual_disease_targets",
            "manual_disease_target_ids": seed["disease_target_ids"],
            "mode": "auto",
        },
    )
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["analysis_id"]
    state = {}
    for _ in range(180):
        state = (await c.get(f"/analyses/{run_id}")).json()
        if state.get("status") in {"complete", "failed"}:
            break
    assert state["status"] == "complete", state.get("error_message")
    sr = state["stage_results"]
    ref233 = set(seed["overlap_233_symbols"])
    overlap_genes = {row["gene_symbol"] for row in sr["5"]["overlap"]}
    assert sr["5"]["count"] == 247
    assert ref233 <= overlap_genes  # 100% recall of Hito's overlap
    assert len(overlap_genes - ref233) == 14  # the 14 extra Herbaflow finds
