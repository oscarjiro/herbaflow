"""The durable in-stage edit layer (pure functions).

A *stage edit* records user add/remove decisions for an entity stage as a pair of
disjoint lists. The entity id key is parameterized (``id_key``); it defaults to
``"compound_id"`` (Stage 1), and Stage 3/4 pass ``"target_id"``::

    {"added": [{<id_key>: str, "canonical_name": str | None}], "removed": [str, ...]}

Added entries carry their resolved name so the layer is self-contained — rendering or
reapplying an edit never needs an external lookup. The edit is *durable*: it is applied
on top of whatever the stage computes, so it survives re-runs that recompute the stage
(E6). Re-adding a removed id clears the removal; re-removing an added id clears the add;
``added`` and ``removed`` always end disjoint (E5).
"""

from __future__ import annotations

from typing import Any

_EMPTY_EDIT: dict[str, Any] = {"added": [], "removed": []}


def empty_edit() -> dict[str, Any]:
    """A fresh, empty edit record."""
    return {"added": [], "removed": []}


def _is_empty(edit: dict[str, Any] | None) -> bool:
    return not edit or (not edit.get("added") and not edit.get("removed"))


def normalize_edit(
    existing: dict[str, Any],
    add: list[dict[str, Any]],
    remove: list[str],
    *,
    id_key: str = "compound_id",
) -> dict[str, Any]:
    """Fold ``add``/``remove`` into ``existing``, returning a new disjoint, de-duped edit.

    - Adding an id currently in ``removed`` clears it from ``removed`` (re-adding undoes a removal).
    - Removing an id currently in ``added`` clears it from ``added`` (re-removing undoes an add).
    - Otherwise the id unions into the respective list. ``added`` is de-duped by ``id_key``;
      the last name wins. ``added`` and ``removed`` end disjoint.
    """
    # Start from copies of the existing state, keyed by id for O(1) updates.
    added: dict[str, dict[str, Any]] = {
        str(e[id_key]): {
            id_key: str(e[id_key]),
            "canonical_name": e.get("canonical_name"),
        }
        for e in existing.get("added", [])
    }
    removed: set[str] = {str(r) for r in existing.get("removed", [])}

    for entry in add:
        cid = str(entry[id_key])
        removed.discard(cid)  # re-adding clears a pending removal
        added[cid] = {id_key: cid, "canonical_name": entry.get("canonical_name")}

    for rid in remove:
        rid_s = str(rid)
        if rid_s in added:
            del added[rid_s]  # re-removing clears a pending add
        else:
            removed.add(rid_s)

    return {"added": list(added.values()), "removed": sorted(removed)}


def apply_edits(
    computed_ids: list[str], edit: dict[str, Any] | None, *, id_key: str = "compound_id"
) -> dict[str, Any]:
    """Apply ``edit`` to the computed id list, returning ``{effective, tags}``.

    ``effective = (computed ∪ added) − removed`` (order: computed first, then added).
    Tags: a computed id not removed -> ``"computed"``; a computed id removed ->
    ``"user-removed"``; an added id (not already computed) -> ``"user-added"``. Removed
    ids absent from ``computed`` are ignored. Added ids already in ``computed`` keep the
    ``"computed"`` tag.
    """
    edit = edit or _EMPTY_EDIT
    computed = [str(c) for c in computed_ids]
    computed_set = set(computed)
    removed = {str(r) for r in edit.get("removed", [])}
    added_ids = [str(e[id_key]) for e in edit.get("added", [])]

    tags: dict[str, str] = {}
    effective: list[str] = []
    for cid in computed:
        if cid in removed:
            tags[cid] = "user-removed"
        else:
            tags[cid] = "computed"
            effective.append(cid)
    for aid in added_ids:
        if aid in computed_set:
            # Already computed — normalization makes this rare; keep it computed/effective.
            continue
        tags[aid] = "user-added"
        if aid not in effective:
            effective.append(aid)
    return {"effective": effective, "tags": tags}


def build_stage_entities(
    computed_entities: list[dict[str, Any]],
    edit: dict[str, Any] | None,
    *,
    id_key: str = "compound_id",
    list_key: str = "compounds",
) -> dict[str, Any]:
    """Build the stored entity-stage fragment from raw computed entities + an edit.

    ``computed_entities`` is the raw runner output: a list of
    ``{<id_key>, canonical_name, ...}``.
    Returns ``{<list_key>, computed_ids, count, state}`` where ``<list_key>`` is the tagged list
    (computed entries first — each tagged ``"computed"`` or ``"user-removed"`` — followed by
    added entries tagged ``"user-added"``, names from the edit). The effective forward set is the
    entries with ``tag != "user-removed"``; ``count`` is its size. ``state`` is ``"user_provided"``
    iff the edit is non-empty, else ``"computed"``.
    """
    computed_ids = [str(e[id_key]) for e in computed_entities]
    names: dict[str, str | None] = {
        str(e[id_key]): e.get("canonical_name") for e in computed_entities
    }
    applied = apply_edits(computed_ids, edit, id_key=id_key)
    tags = applied["tags"]

    entities: list[dict[str, Any]] = []
    for cid in computed_ids:
        entities.append({id_key: cid, "canonical_name": names.get(cid), "tag": tags[cid]})
    for entry in (edit or _EMPTY_EDIT).get("added", []):
        aid = str(entry[id_key])
        if aid in names:
            # Already represented as a computed entry above.
            continue
        entities.append(
            {
                id_key: aid,
                "canonical_name": entry.get("canonical_name"),
                "tag": "user-added",
            }
        )

    count = sum(1 for c in entities if c["tag"] != "user-removed")
    state = "computed" if _is_empty(edit) else "user_provided"
    return {
        list_key: entities,
        "computed_ids": computed_ids,
        "count": count,
        "state": state,
    }
