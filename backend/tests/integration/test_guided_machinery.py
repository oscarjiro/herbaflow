"""Integration tests for the guided machinery: reset-from and stage-edit endpoints.

All scenarios use the seeded compounds (c1/c2) — no 2,000-compound seeding.
"""

from __future__ import annotations

import uuid

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SETTLED = frozenset(
    {"complete", "failed", "stage_1_awaiting_approval", "stage_2_awaiting_approval"}
)


async def _poll(c, run_id: str, *, until=None, max_iters: int = 80) -> dict:
    """Poll GET /analyses/{id} until settled (or a specific status is reached)."""
    final = {}
    for _ in range(max_iters):
        r = await c.get(f"/analyses/{run_id}")
        final = r.json()
        st = final.get("status")
        if until is not None and st == until:
            break
        if until is None and st in SETTLED:
            break
    return final


async def _create(c, ids, *, mode: str = "guided", plant: str = "plant_full", manual=None):
    body = {
        "plant_ids": [str(ids[plant])],
        "disease_id": str(ids["disease"]),
        "mode": mode,
    }
    if manual:
        body["manual_compound_ids"] = [str(m) for m in manual]
    resp = await c.post("/analyses", json=body)
    assert resp.status_code == 202
    return resp.json()["analysis_id"]


# ---------------------------------------------------------------------------
# E6 — Edit S1 + reset-from S2 (edit layer survives param Redo)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_s1_add_remove_and_reset_from_s2_edit_layer_survives(client) -> None:
    """
    Scenario E6:
    1. Create guided run on plant_empty with c1 as manual compound -> S1 awaiting (c1 effective).
    2. Stage-edit S1: add c2, remove c1 -> a guided edit of the CURRENT awaiting stage re-parks
       AT stage_1_awaiting_approval (it must not advance past S1's own checkpoint); c2 effective,
       c1 tagged user-removed. Then Approve to advance into stage_2_awaiting_approval.
    3. reset-from/2 with skip_adme=true -> re-run from S2 again; S1 edit layer survives (c2
       effective, c1 user-removed) and parameters["stage_edits"]["1"] is preserved.
    """
    c, ids = client

    # Step 1: guided, plant_empty + manual c1
    run_id = await _create(c, ids, mode="guided", plant="plant_empty", manual=[ids["c1"]])
    state = await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert state["status"] == "stage_1_awaiting_approval"
    assert any(
        comp["compound_id"] == str(ids["c1"])
        for comp in state["stage_results"]["1"]["compounds"]
        if comp.get("tag") != "user-removed"
    ), "c1 should be effective in S1 before edit"

    # Step 2: edit S1 — add c2, remove c1. A guided edit of the current awaiting stage
    # re-parks AT S1 (it must not advance past S1's own checkpoint).
    edit_resp = await c.post(
        f"/analyses/{run_id}/stages/1/edit",
        json={"add": [str(ids["c2"])], "remove": [str(ids["c1"])]},
    )
    assert edit_resp.status_code == 202
    state = await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert state["status"] == "stage_1_awaiting_approval"

    s1_compounds = state["stage_results"]["1"]["compounds"]
    c2_entries = [x for x in s1_compounds if x["compound_id"] == str(ids["c2"])]
    c1_entries = [x for x in s1_compounds if x["compound_id"] == str(ids["c1"])]
    assert c2_entries, "c2 should be in S1 after edit"
    assert c2_entries[0].get("tag") != "user-removed", "c2 should be effective"
    assert c1_entries, "c1 should remain in S1 compounds list (tagged user-removed)"
    assert c1_entries[0].get("tag") == "user-removed", "c1 should be tagged user-removed"

    # The edit did NOT run S2: S1 is fresh (not stale) and S2 has no result yet.
    assert not state["stage_results"]["1"].get("stale"), "S1 must not be stale after editing it"
    assert "2" not in state["stage_results"], "edit of current stage must not run S2"

    # Approve S1 to advance into S2 (the edit did not auto-advance past the checkpoint).
    adv = await c.post(f"/analyses/{run_id}/advance")
    assert adv.status_code == 202
    state = await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert state["status"] == "stage_2_awaiting_approval"

    # Step 3: reset-from/2 with skip_adme=true — edit layer must survive
    reset_resp = await c.post(
        f"/analyses/{run_id}/reset-from/2",
        json={"parameters": {"2": {"skip_adme": True}}},
    )
    assert reset_resp.status_code == 202
    state = await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert state["status"] == "stage_2_awaiting_approval"

    # S1 edit layer must be preserved after the S2 re-run.
    s1_after = state["stage_results"]["1"]["compounds"]
    c2_after = [x for x in s1_after if x["compound_id"] == str(ids["c2"])]
    c1_after = [x for x in s1_after if x["compound_id"] == str(ids["c1"])]
    assert c2_after and c2_after[0].get("tag") != "user-removed", "c2 still effective after S2 redo"
    assert (
        c1_after and c1_after[0].get("tag") == "user-removed"
    ), "c1 still user-removed after S2 redo"

    # parameters["stage_edits"]["1"] must be persisted.
    assert "stage_edits" in state["parameters"], "stage_edits key must exist in parameters"
    assert "1" in state["parameters"]["stage_edits"], "stage_edits['1'] must survive S2 param Redo"


# ---------------------------------------------------------------------------
# Zero-pass S2 guided — checkpoint, not failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_pass_s2_guided_is_checkpoint_not_failure(client) -> None:
    """
    For a guided run, a zero-pass S2 (all compounds fail ADME) must land at
    stage_2_awaiting_approval — NOT failed.  A subsequent reset-from with
    skip_adme=true must recover (compounds pass again).
    """
    c, ids = client

    run_id = await _create(c, ids, mode="guided", plant="plant_full")
    # Poll to S1 checkpoint then advance.
    state = await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert state["status"] == "stage_1_awaiting_approval"
    adv = await c.post(f"/analyses/{run_id}/advance")
    assert adv.status_code == 202
    state = await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert state["status"] == "stage_2_awaiting_approval"

    # Reset with max_mw=1 AND max_violations=0 -> every compound fails ADME -> zero-pass.
    # (max_violations default is 1, so max_mw=1 alone still allows 1 violation — we need 0.)
    reset_resp = await c.post(
        f"/analyses/{run_id}/reset-from/2",
        json={"parameters": {"2": {"max_mw": 1, "max_violations": 0}}},
    )
    assert reset_resp.status_code == 202
    state = await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert (
        state["status"] == "stage_2_awaiting_approval"
    ), "Guided zero-pass S2 must be a checkpoint, not a hard failure"
    assert (
        state["stage_results"]["2"]["count"] == 0
    ), "No compounds should pass with max_mw=1 and max_violations=0"

    # Recovery: reset with skip_adme=true -> both compounds pass.
    recover_resp = await c.post(
        f"/analyses/{run_id}/reset-from/2",
        json={"parameters": {"2": {"skip_adme": True}}},
    )
    assert recover_resp.status_code == 202
    state = await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert state["status"] == "stage_2_awaiting_approval"
    assert state["stage_results"]["2"]["count"] == 2, "Both compounds pass with skip_adme=true"


# ---------------------------------------------------------------------------
# Zero-pass S2 auto — hard failure with skip_adme hint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_pass_s2_auto_is_hard_failure(client) -> None:
    """
    For an auto run, a zero-pass S2 (all compounds fail ADME) must hard-fail
    and the error message must mention skip_adme.
    """
    c, ids = client

    run_id = await _create(c, ids, mode="auto", plant="plant_full")
    # The seeded compounds have no findable targets, so an auto run now hard-stops at the
    # empty S3 (don't-waste-downstream). That settled (failed) state is enough to reset-from-2
    # and exercise the S2 zero-pass path that this test is actually about.
    state = await _poll(c, run_id)
    assert state["status"] in {"complete", "failed"}

    # Trigger a zero-pass S2 via reset-from.
    # Use max_mw=1 + max_violations=0 so all compounds fail (default max_violations=1 would
    # allow one violation, meaning a compound with MW=46.07 still passes with max_mw=1 alone).
    reset_resp = await c.post(
        f"/analyses/{run_id}/reset-from/2",
        json={"parameters": {"2": {"max_mw": 1, "max_violations": 0}}},
    )
    assert reset_resp.status_code == 202
    state = await _poll(c, run_id)
    assert state["status"] == "failed", "Auto zero-pass S2 must hard-fail (no guided checkpoint)"
    assert (
        "skip_adme" in state["error_message"].lower()
    ), "Error message must mention skip_adme as a recovery hint"


# ---------------------------------------------------------------------------
# 422 — unknown compound id in stage-edit add
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_stage_422_on_unknown_add_id(client) -> None:
    """POST /stages/1/edit with an unknown compound UUID returns 422 problem+json."""
    c, ids = client

    run_id = await _create(c, ids, mode="guided", plant="plant_full")
    state = await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert state["status"] == "stage_1_awaiting_approval"

    unknown = uuid.uuid4()
    resp = await c.post(
        f"/analyses/{run_id}/stages/1/edit",
        json={"add": [str(unknown)], "remove": []},
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 422
    assert str(unknown) in body.get("invalid_compound_ids", [])


# ---------------------------------------------------------------------------
# 422 — an edit may never empty a stage (remove the last remaining entity)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_last_compound_is_rejected(client) -> None:
    """An edit may never empty a stage: removing the last remaining entity is
    rejected (422) and the run is left untouched."""
    c, ids = client
    run_id = await _create(c, ids, mode="guided", plant="plant_empty", manual=[ids["c1"]])
    state = await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert state["stage_results"]["1"]["count"] == 1

    resp = await c.post(
        f"/analyses/{run_id}/stages/1/edit",
        json={"add": [], "remove": [str(ids["c1"])]},
    )
    assert resp.status_code == 422

    after = (await c.get(f"/analyses/{run_id}")).json()
    assert after["status"] == "stage_1_awaiting_approval"
    assert after["stage_results"]["1"]["count"] == 1


# ---------------------------------------------------------------------------
# Upstream edit while parked at S2 → stale → 409 → reset-from → recomputed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upstream_edit_stages_stale_then_reset_recomputes(client) -> None:
    """Parked at S2, edit S1: S2 is marked stale and NOT re-run; advance is refused (409);
    an explicit reset-from/1 recomputes and clears the stale flag."""
    c, ids = client

    # Guided run with plant_empty + c1 manual → parks at stage_1_awaiting_approval.
    run_id = await _create(c, ids, mode="guided", plant="plant_empty", manual=[ids["c1"]])
    await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert (await c.post(f"/analyses/{run_id}/advance")).status_code == 202
    await _poll(c, run_id, until="stage_2_awaiting_approval")

    # Edit S1 (add c2) while parked at S2 — stages the change, does NOT re-run.
    edit = await c.post(
        f"/analyses/{run_id}/stages/1/edit",
        json={"add": [str(ids["c2"])], "remove": []},
    )
    assert edit.status_code == 202
    state = (await c.get(f"/analyses/{run_id}")).json()
    assert (
        state["status"] == "stage_2_awaiting_approval"
    ), "run must stay parked at S2 after upstream edit"
    assert state["stage_results"]["2"].get("stale") is True, "S2 must be flagged stale"
    assert state["parameters"]["rerun_from"] == 1, "rerun_from must record the edited stage number"

    # Approve is refused while a downstream stage is stale.
    blocked = await c.post(f"/analyses/{run_id}/advance")
    assert blocked.status_code == 409

    # Explicit reset-from/1 re-runs S2 and clears stale + rerun_from.
    assert (await c.post(f"/analyses/{run_id}/reset-from/1", json={})).status_code == 202
    state = await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert state["stage_results"]["2"].get("stale") in (
        None,
        False,
    ), "stale must be cleared after reset"
    assert "rerun_from" not in state["parameters"], "rerun_from must be removed after reset"

    # c2 (the staged add) is now in the screened S1 result.
    c2_eff = [
        x
        for x in state["stage_results"]["1"]["compounds"]
        if x["compound_id"] == str(ids["c2"]) and x.get("tag") != "user-removed"
    ]
    assert c2_eff, "c2 must be effective in S1 after reset-from recomputes"
