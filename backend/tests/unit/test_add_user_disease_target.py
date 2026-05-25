import pytest
import copy

from app.routers.analyses import _add_target_to_stage4, _remove_target_from_stage4


def _make_stage4(targets=None):
    """Minimal stage4 result dict."""
    targets = targets or [
        {
            "gene_symbol": "TNF",
            "uniprot_id": "P01375",
            "association_score": 0.85,
            "disease_name": "Rheumatoid arthritis",
            "source": "db_cache",
        }
    ]
    return {
        "disease_target_count": len(targets),
        "disease_gene_symbols": [t["gene_symbol"] for t in targets],
        "targets": copy.deepcopy(targets),
    }


# --- _add_target_to_stage4 ---

def test_add_disease_target_injects_entry():
    stage4 = _make_stage4()
    result = _add_target_to_stage4(stage4, "EGFR", "P00533", None, "Rheumatoid arthritis")
    genes = [t["gene_symbol"] for t in result["targets"]]
    assert "EGFR" in genes
    egfr = next(t for t in result["targets"] if t["gene_symbol"] == "EGFR")
    assert egfr["source"] == "user_provided"
    assert egfr["association_score"] == 1.0
    assert egfr["disease_name"] == "Rheumatoid arthritis"
    assert egfr["protein_name"] is None


def test_add_disease_target_increments_count():
    result = _add_target_to_stage4(_make_stage4(), "EGFR", "P00533", None, "RA")
    assert result["disease_target_count"] == 2
    assert "EGFR" in result["disease_gene_symbols"]


def test_add_disease_target_sets_user_modified():
    result = _add_target_to_stage4(_make_stage4(), "EGFR", "P00533", None, "RA")
    assert result["user_modified"] is True


def test_add_disease_target_rejects_duplicate():
    with pytest.raises(ValueError, match="already in Stage 4"):
        _add_target_to_stage4(_make_stage4(), "TNF", "P01375", None, "RA")


def test_add_disease_target_case_insensitive_duplicate():
    with pytest.raises(ValueError, match="already in Stage 4"):
        _add_target_to_stage4(_make_stage4(), "tnf", "P01375", None, "RA")


def test_add_disease_target_does_not_mutate_input():
    stage4 = _make_stage4()
    original_count = stage4["disease_target_count"]
    _add_target_to_stage4(stage4, "EGFR", "P00533", None, "RA")
    assert stage4["disease_target_count"] == original_count


# --- _remove_target_from_stage4 ---

def test_remove_disease_target_removes_entry():
    stage4 = _make_stage4()
    result = _remove_target_from_stage4(stage4, "TNF")
    assert result["targets"] == []
    assert result["disease_target_count"] == 0
    assert "TNF" not in result["disease_gene_symbols"]


def test_remove_disease_target_sets_user_modified():
    result = _remove_target_from_stage4(_make_stage4(), "TNF")
    assert result["user_modified"] is True


def test_remove_disease_target_case_insensitive():
    result = _remove_target_from_stage4(_make_stage4(), "tnf")
    assert result["disease_target_count"] == 0


def test_remove_disease_target_raises_if_missing():
    with pytest.raises(KeyError, match="EGFR not found in Stage 4"):
        _remove_target_from_stage4(_make_stage4(), "EGFR")


def test_remove_disease_target_does_not_mutate_input():
    stage4 = _make_stage4()
    original_count = stage4["disease_target_count"]
    _remove_target_from_stage4(stage4, "TNF")
    assert stage4["disease_target_count"] == original_count
