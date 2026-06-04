import copy

import pytest
from app.routers.analyses import _add_target_to_stage3, _remove_target_from_stage3


def _make_stage3(targets=None):
    """Minimal stage3 result dict."""
    targets = targets or [
        {
            "gene_symbol": "TP53",
            "uniprot_id": "P04637",
            "compound_count": 2,
            "compound_ids": ["cid-A", "cid-B"],
            "source": "chembl",
        }
    ]
    return {
        "target_count": len(targets),
        "targets": copy.deepcopy(targets),
        "target_gene_symbols": [t["gene_symbol"] for t in targets],
        "target_compound_map": {t["gene_symbol"]: t["compound_ids"] for t in targets},
        "covered": 2,
        "no_data": 0,
        "coverage_pct": 100.0,
        "compound_sources": {"cid-A": ["chembl"], "cid-B": ["chembl"]},
        "uncovered_compounds": [],
    }


# --- _add_target_to_stage3 ---

def test_add_target_injects_entry():
    stage3 = _make_stage3()
    result = _add_target_to_stage3(stage3, "EGFR", "P00533", "Epidermal growth factor receptor")
    genes = [t["gene_symbol"] for t in result["targets"]]
    assert "EGFR" in genes
    egfr = next(t for t in result["targets"] if t["gene_symbol"] == "EGFR")
    assert egfr["source"] == "user_provided"
    assert egfr["compound_count"] == 0
    assert egfr["compound_ids"] == []
    assert egfr["uniprot_id"] == "P00533"
    assert egfr["protein_name"] == "Epidermal growth factor receptor"


def test_add_target_increments_count():
    stage3 = _make_stage3()
    result = _add_target_to_stage3(stage3, "EGFR", "P00533", None)
    assert result["target_count"] == 2
    assert "EGFR" in result["target_gene_symbols"]


def test_add_target_sets_user_modified():
    result = _add_target_to_stage3(_make_stage3(), "EGFR", "P00533", None)
    assert result["user_modified"] is True


def test_add_target_rejects_duplicate_gene():
    with pytest.raises(ValueError, match="already in Stage 3"):
        _add_target_to_stage3(_make_stage3(), "TP53", "P04637", None)


def test_add_target_case_insensitive_duplicate():
    with pytest.raises(ValueError):
        _add_target_to_stage3(_make_stage3(), "tp53", "P04637", None)


def test_add_target_does_not_mutate_input():
    stage3 = _make_stage3()
    original_count = stage3["target_count"]
    _add_target_to_stage3(stage3, "EGFR", "P00533", None)
    assert stage3["target_count"] == original_count


# --- _remove_target_from_stage3 ---

def test_remove_target_removes_entry():
    stage3 = _make_stage3()
    result = _remove_target_from_stage3(stage3, "TP53")
    assert result["targets"] == []
    assert result["target_count"] == 0
    assert "TP53" not in result["target_gene_symbols"]


def test_remove_target_sets_user_modified():
    result = _remove_target_from_stage3(_make_stage3(), "TP53")
    assert result["user_modified"] is True


def test_remove_target_case_insensitive():
    result = _remove_target_from_stage3(_make_stage3(), "tp53")
    assert result["target_count"] == 0


def test_remove_target_raises_keyerror_if_missing():
    with pytest.raises(KeyError, match="EGFR not found in Stage 3"):
        _remove_target_from_stage3(_make_stage3(), "EGFR")


def test_remove_target_does_not_mutate_input():
    stage3 = _make_stage3()
    original_count = stage3["target_count"]
    _remove_target_from_stage3(stage3, "TP53")
    assert stage3["target_count"] == original_count
