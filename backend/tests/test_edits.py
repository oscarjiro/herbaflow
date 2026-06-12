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
