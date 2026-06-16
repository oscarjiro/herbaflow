"""GD-1 golden regression: curcumin x colorectal cancer, auto mode, all 8 stages, OFFLINE.

Level-A deterministic snapshot test (opt-in ``@pytest.mark.scientific``, deselected by default).
Seeds the captured canonical data, replays the recorded STRING + g:Profiler responses, drives a
manual-single-compound x selected-disease run end-to-end, and asserts a frozen snapshot of the
scientific output (overlap count, MCC hub ranking, enrichment terms). Stage 3 stays fully offline
via D9 edge-reuse; the Stage-3 client guards in ``patch_gd1`` prove no live call is made.
"""

import pytest

from tests.scientific.conftest import load_json, poll_run
from tests.scientific.gd1_support import patch_gd1, seed_gd1

pytestmark = pytest.mark.scientific


@pytest.mark.asyncio
async def test_gd1_curcumin_crc_snapshot(golden_client, monkeypatch):
    c, engine = golden_client
    seed = await seed_gd1(engine)
    patch_gd1(monkeypatch)
    snap = load_json("gd1_snapshot.json")

    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_compounds",
            "manual_compound_ids": [seed["curcumin_compound_id"]],
            "disease_input_mode": "selection",
            "disease_id": seed["disease_id"],
            "mode": "auto",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    state = await poll_run(c, run_id)
    assert state["status"] == "complete", state.get("error_message")

    sr = state["stage_results"]

    # Stage 5 — raw overlap (no statistics): the field-standard set intersection.
    assert sr["5"]["count"] == snap["overlap_count"]
    for k in snap["stage5_forbidden_keys"]:
        assert k not in sr["5"]

    # Stage 7 — MCC hub ranking (Chin 2014), sole ranker.
    assert sr["7"]["ranking_metric"] == snap["ranking_metric"]
    hubs = [h["gene_symbol"] for h in sorted(sr["7"]["hubs"], key=lambda h: -h["mcc"])]
    assert hubs[:5] == snap["mcc_top5"]

    # Stage 8 — functional enrichment includes the disease pathway.
    enr = {t["name"] for t in sr["8"]["terms"]}
    for term in snap["enrichment_includes"]:
        assert term in enr
