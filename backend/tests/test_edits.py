"""Tests for gene-identity carry-through on user-added target entries.

Covers:
- normalize_edit preserves carry-fields (gene_symbol, uniprot_accession) on added entries
- build_stage_entities carries them into the output row for user-added entries
- Compound added entries are unaffected (no spurious carry-field keys)
"""

from __future__ import annotations


def test_added_target_carries_gene_identity() -> None:
    from app.pipeline import edits

    edit = edits.normalize_edit(
        edits.empty_edit(),
        add=[
            {
                "target_id": "t1",
                "canonical_name": "EGFR",
                "gene_symbol": "EGFR",
                "uniprot_accession": "P00533",
            }
        ],
        remove=[],
        id_key="target_id",
    )
    assert edit["added"][0]["gene_symbol"] == "EGFR"
    assert edit["added"][0]["uniprot_accession"] == "P00533"

    frag = edits.build_stage_entities([], edit, id_key="target_id", list_key="targets")
    row = frag["targets"][0]
    assert row["target_id"] == "t1"
    assert row["gene_symbol"] == "EGFR"
    assert row["uniprot_accession"] == "P00533"
    assert row["tag"] == "user-added"
    assert frag["state"] == "user_provided"


def test_added_compound_unaffected() -> None:
    from app.pipeline import edits

    edit = edits.normalize_edit(
        edits.empty_edit(),
        add=[{"compound_id": "c1", "canonical_name": "aspirin"}],
        remove=[],
    )
    frag = edits.build_stage_entities([], edit, id_key="compound_id", list_key="compounds")
    row = frag["compounds"][0]
    assert row["compound_id"] == "c1"
    assert "gene_symbol" not in row  # compounds carry no carry-fields


def test_computed_row_preserves_all_runner_fields() -> None:
    """The edit layer carries WHATEVER the runner attaches to each computed row (not a
    two-field allowlist): Stage 4 emits score / association_type / source_url, and they must
    survive the fold so Stage 5/6 see the disease association score."""
    from app.pipeline import edits

    frag = edits.build_stage_entities(
        [
            {
                "target_id": "t1",
                "canonical_name": "EGFR",
                "gene_symbol": "EGFR",
                "uniprot_accession": "P00533",
                "score": 0.9,
                "association_type": "open_targets_overall",
                "source_url": "https://example/P00533",
            }
        ],
        edits.empty_edit(),
        id_key="target_id",
        list_key="targets",
    )
    row = frag["targets"][0]
    assert row["score"] == 0.9
    assert row["association_type"] == "open_targets_overall"
    assert row["source_url"] == "https://example/P00533"
    assert row["gene_symbol"] == "EGFR"
    assert row["canonical_name"] == "EGFR"
    assert row["tag"] == "computed"


def test_compound_row_shape_stays_minimal() -> None:
    """Regression: a compound computed row (runner attaches nothing extra) stays exactly
    {compound_id, canonical_name, tag} — the generalized carry must NOT add keys."""
    from app.pipeline import edits

    frag = edits.build_stage_entities(
        [{"compound_id": "c1", "canonical_name": "Alpha"}],
        edits.empty_edit(),
        id_key="compound_id",
        list_key="compounds",
    )
    row = frag["compounds"][0]
    assert set(row) == {"compound_id", "canonical_name", "tag"}
