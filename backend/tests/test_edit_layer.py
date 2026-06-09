"""Pure unit tests for the durable in-stage edit layer (app.pipeline.edits).

Covers the edit normalization algebra (E5 — re-add clears a removal, re-remove
clears an add, disjoint added/removed) and the reapply-on-recompute behaviour
(E6 — an add survives a fresh computed set that drops it; a removal re-suppresses
an id the fresh set re-introduces).
"""

from __future__ import annotations

from app.pipeline import edits


def _eid(n: int) -> str:
    # Stable, readable id strings for the pure tests.
    return f"00000000-0000-0000-0000-0000000000{n:02d}"


# ---------------------------------------------------------------------------
# normalize_edit
# ---------------------------------------------------------------------------
def test_add_new_id_unions_into_added() -> None:
    a = _eid(1)
    out = edits.normalize_edit(
        {"added": [], "removed": []}, [{"compound_id": a, "canonical_name": "Curcumin"}], []
    )
    assert out["added"] == [{"compound_id": a, "canonical_name": "Curcumin"}]
    assert out["removed"] == []


def test_remove_new_id_unions_into_removed() -> None:
    a = _eid(1)
    out = edits.normalize_edit({"added": [], "removed": []}, [], [a])
    assert out["removed"] == [a]
    assert out["added"] == []


def test_re_add_a_removed_id_clears_the_removal() -> None:
    a = _eid(1)
    existing = {"added": [], "removed": [a]}
    out = edits.normalize_edit(existing, [{"compound_id": a, "canonical_name": "X"}], [])
    assert out["removed"] == []
    assert out["added"] == [{"compound_id": a, "canonical_name": "X"}]


def test_re_remove_an_added_id_clears_the_add() -> None:
    a = _eid(1)
    existing = {"added": [{"compound_id": a, "canonical_name": "X"}], "removed": []}
    out = edits.normalize_edit(existing, [], [a])
    assert out["added"] == []
    assert out["removed"] == []


def test_added_and_removed_stay_disjoint() -> None:
    a, b = _eid(1), _eid(2)
    existing = {"added": [{"compound_id": a, "canonical_name": "A"}], "removed": [b]}
    # Add b (currently removed) and remove a (currently added): both cross out.
    out = edits.normalize_edit(existing, [{"compound_id": b, "canonical_name": "B"}], [a])
    added_ids = {e["compound_id"] for e in out["added"]}
    removed_ids = set(out["removed"])
    assert added_ids & removed_ids == set()
    assert added_ids == {b}
    assert removed_ids == set()


def test_add_dedupes_by_compound_id() -> None:
    a = _eid(1)
    existing = {"added": [{"compound_id": a, "canonical_name": "A"}], "removed": []}
    out = edits.normalize_edit(existing, [{"compound_id": a, "canonical_name": "A2"}], [])
    assert len([e for e in out["added"] if e["compound_id"] == a]) == 1


# ---------------------------------------------------------------------------
# apply_edits
# ---------------------------------------------------------------------------
def test_apply_add_new_id_is_effective_and_user_added() -> None:
    computed = [_eid(1)]
    a = _eid(9)
    edit = {"added": [{"compound_id": a, "canonical_name": "New"}], "removed": []}
    out = edits.apply_edits(computed, edit)
    assert a in out["effective"]
    assert out["tags"][a] == "user-added"
    assert out["tags"][_eid(1)] == "computed"


def test_apply_remove_computed_id_excludes_but_tags_user_removed() -> None:
    computed = [_eid(1), _eid(2)]
    edit = {"added": [], "removed": [_eid(2)]}
    out = edits.apply_edits(computed, edit)
    assert _eid(2) not in out["effective"]
    assert out["tags"][_eid(2)] == "user-removed"
    assert out["tags"][_eid(1)] == "computed"


def test_apply_removed_id_not_in_computed_is_ignored() -> None:
    computed = [_eid(1)]
    edit = {"added": [], "removed": [_eid(5)]}
    out = edits.apply_edits(computed, edit)
    assert out["effective"] == [_eid(1)]
    assert _eid(5) not in out["tags"]


# ---------------------------------------------------------------------------
# build_stage_entities — E6 reapply-on-recompute
# ---------------------------------------------------------------------------
def test_build_stage_entities_no_edit_is_all_computed() -> None:
    computed_entities = [
        {"compound_id": _eid(1), "canonical_name": "A"},
        {"compound_id": _eid(2), "canonical_name": "B"},
    ]
    frag = edits.build_stage_entities(computed_entities, None)
    assert frag["count"] == 2
    assert frag["state"] == "computed"
    assert frag["computed_ids"] == [_eid(1), _eid(2)]
    assert all(c["tag"] == "computed" for c in frag["compounds"])


def test_e6a_added_id_reapplied_over_fresh_set_without_it() -> None:
    # Fresh computed set does NOT contain the previously-added id -> the add is re-applied.
    a = _eid(9)
    fresh = [{"compound_id": _eid(1), "canonical_name": "A"}]
    edit = {"added": [{"compound_id": a, "canonical_name": "Added"}], "removed": []}
    frag = edits.build_stage_entities(fresh, edit)
    ids = {c["compound_id"]: c for c in frag["compounds"]}
    assert ids[a]["tag"] == "user-added"
    assert ids[a]["canonical_name"] == "Added"
    effective = [c["compound_id"] for c in frag["compounds"] if c["tag"] != "user-removed"]
    assert a in effective
    assert frag["count"] == 2
    assert frag["state"] == "user_provided"


def test_e6b_removed_id_resuppressed_over_fresh_set_with_it() -> None:
    # Fresh computed set re-introduces a previously-removed id -> it is re-suppressed.
    r = _eid(2)
    fresh = [
        {"compound_id": _eid(1), "canonical_name": "A"},
        {"compound_id": r, "canonical_name": "B"},
    ]
    edit = {"added": [], "removed": [r]}
    frag = edits.build_stage_entities(fresh, edit)
    ids = {c["compound_id"]: c for c in frag["compounds"]}
    assert ids[r]["tag"] == "user-removed"
    effective = [c["compound_id"] for c in frag["compounds"] if c["tag"] != "user-removed"]
    assert r not in effective
    assert frag["count"] == 1
    assert frag["state"] == "user_provided"


def test_build_stage_entities_count_is_effective_forward_set() -> None:
    # 2 computed, remove 1, add 1 -> effective = 2.
    fresh = [
        {"compound_id": _eid(1), "canonical_name": "A"},
        {"compound_id": _eid(2), "canonical_name": "B"},
    ]
    edit = {
        "added": [{"compound_id": _eid(9), "canonical_name": "New"}],
        "removed": [_eid(2)],
    }
    frag = edits.build_stage_entities(fresh, edit)
    assert frag["count"] == 2


# ---------------------------------------------------------------------------
# Entity-keyed variant (id_key="target_id", list_key="targets") — Stage 3/4.
# The same algebra must hold with the target id key and the result fragment must
# expose the tagged list under "targets", never "compounds".
# ---------------------------------------------------------------------------
def test_normalize_edit_target_id_key() -> None:
    a, b = _eid(1), _eid(2)
    existing = {"added": [{"target_id": a, "canonical_name": "EGFR"}], "removed": [b]}
    # Add b (currently removed) and remove a (currently added): both cross out (E5 disjoint).
    out = edits.normalize_edit(
        existing, [{"target_id": b, "canonical_name": "TP53"}], [a], id_key="target_id"
    )
    added_ids = {e["target_id"] for e in out["added"]}
    removed_ids = set(out["removed"])
    assert added_ids & removed_ids == set()
    assert added_ids == {b}
    assert removed_ids == set()
    assert out["added"] == [{"target_id": b, "canonical_name": "TP53"}]


def test_apply_edits_target_id_key() -> None:
    computed = [_eid(1), _eid(2)]
    edit = {
        "added": [{"target_id": _eid(9), "canonical_name": "New"}],
        "removed": [_eid(2)],
    }
    out = edits.apply_edits(computed, edit, id_key="target_id")
    assert _eid(9) in out["effective"]
    assert out["tags"][_eid(9)] == "user-added"
    assert out["tags"][_eid(2)] == "user-removed"
    assert out["tags"][_eid(1)] == "computed"
    assert _eid(2) not in out["effective"]


def test_build_stage_entities_targets_list_key_and_tags() -> None:
    # 2 computed targets, remove 1, add 1 -> tagged list lives under "targets", count = 2.
    fresh = [
        {"target_id": _eid(1), "canonical_name": "EGFR"},
        {"target_id": _eid(2), "canonical_name": "TP53"},
    ]
    edit = {
        "added": [{"target_id": _eid(9), "canonical_name": "AKT1"}],
        "removed": [_eid(2)],
    }
    frag = edits.build_stage_entities(fresh, edit, id_key="target_id", list_key="targets")
    assert "targets" in frag
    assert "compounds" not in frag
    rows = {t["target_id"]: t for t in frag["targets"]}
    assert rows[_eid(1)]["tag"] == "computed"
    assert rows[_eid(2)]["tag"] == "user-removed"
    assert rows[_eid(9)]["tag"] == "user-added"
    assert rows[_eid(9)]["canonical_name"] == "AKT1"
    assert frag["computed_ids"] == [_eid(1), _eid(2)]
    assert frag["count"] == 2
    assert frag["state"] == "user_provided"


def test_build_stage_entities_targets_no_edit_is_all_computed() -> None:
    fresh = [
        {"target_id": _eid(1), "canonical_name": "EGFR"},
        {"target_id": _eid(2), "canonical_name": "TP53"},
    ]
    frag = edits.build_stage_entities(fresh, None, id_key="target_id", list_key="targets")
    assert frag["count"] == 2
    assert frag["state"] == "computed"
    assert frag["computed_ids"] == [_eid(1), _eid(2)]
    assert all(t["tag"] == "computed" for t in frag["targets"])


def test_e6_target_add_reapplied_and_remove_resuppressed() -> None:
    # Fresh set drops the added id (re-applied) and re-introduces the removed id (re-suppressed).
    added = _eid(9)
    removed = _eid(2)
    fresh = [
        {"target_id": _eid(1), "canonical_name": "EGFR"},
        {"target_id": removed, "canonical_name": "TP53"},
    ]
    edit = {
        "added": [{"target_id": added, "canonical_name": "AKT1"}],
        "removed": [removed],
    }
    frag = edits.build_stage_entities(fresh, edit, id_key="target_id", list_key="targets")
    rows = {t["target_id"]: t for t in frag["targets"]}
    assert rows[added]["tag"] == "user-added"
    assert rows[removed]["tag"] == "user-removed"
    effective = [t["target_id"] for t in frag["targets"] if t["tag"] != "user-removed"]
    assert added in effective
    assert removed not in effective
    assert frag["count"] == 2
