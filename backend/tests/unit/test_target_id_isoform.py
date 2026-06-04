"""Tests for isoform-folding target id parity between stage3 and the canonicalization core."""
from __future__ import annotations

from types import SimpleNamespace

import app.services.target_dedup as target_dedup
import pytest
from analysis.stages.stage3_targets import TARGET_NS, _make_target_id
from app.services.canonicalize import (
    TARGET_NS as CORE_TARGET_NS,
)
from app.services.canonicalize import (
    make_target_id,
    target_canonical_key,
)


def test_stage3_target_ns_is_the_core_ns():
    assert TARGET_NS == CORE_TARGET_NS


def test_target_id_and_canonical_key_derive_from_same_folded_form():
    # An isoform accession must produce a target_id and canonical_key that agree:
    # id = uuid5(NS, key). If a caller builds the key unfolded ("uniprot:P04637-2")
    # while the id folds ("uniprot:P04637"), the row is internally inconsistent.
    import uuid

    key = target_canonical_key("P04637-2")
    assert key == "uniprot:P04637"  # folded
    assert make_target_id("P04637-2") == str(uuid.uuid5(CORE_TARGET_NS, key))
    # parent and isoform collapse to the same (id, key) pair
    assert target_canonical_key("P04637") == target_canonical_key("P04637-2")


def test_validated_target_id_matches_core_and_folds_isoform():
    assert _make_target_id("P04637", "TP53") == make_target_id("P04637")
    assert _make_target_id("P04637", "TP53") == "9c4b3fe6-955c-5daf-8717-0e254a7ff9da"
    assert _make_target_id("P04637-2", "TP53") == "9c4b3fe6-955c-5daf-8717-0e254a7ff9da"


def test_accessionless_target_keeps_gene_fallback():
    # pipeline auto-discovery (no UniProt accession) still keys on gene symbol, case-normalized
    assert _make_target_id(None, "TP53") == _make_target_id(None, "tp53")


@pytest.mark.asyncio
async def test_same_protein_mixed_forms_dedupe(monkeypatch):
    async def fake_validate(gene_symbol=None, uniprot_id=None):
        return SimpleNamespace(uniprot_accession="P04637", gene_symbol="TP53")

    monkeypatch.setattr(target_dedup, "validate_human_target", fake_validate)

    submitted = [
        {"gene_symbol": "TP53", "uniprot_id": ""},
        {"gene_symbol": "", "uniprot_id": "P04637"},
        {"gene_symbol": "", "uniprot_id": "P04638"},
    ]
    unique_new, duplicates = await target_dedup.deduplicate_targets(
        submitted=submitted,
        existing_ids=set(),
    )
    # All three resolve to P04637 via fake_validate — exactly ONE unique, TWO duplicates
    assert len(unique_new) + len(duplicates) == len(submitted)  # all inputs resolved, none invalid
    assert len(unique_new) == 1
    assert len(duplicates) == 2
