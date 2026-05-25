import pytest
from app.schemas.import_targets import STPTarget


def _make_stage3(*, covered_cids=None, uncovered_cids=None):
    """Build a minimal stage3 result dict for testing."""
    covered_cids = covered_cids or []
    uncovered_cids = uncovered_cids or []
    targets = [
        {
            "gene_symbol": "TP53",
            "uniprot_id": "P04637",
            "compound_count": len(covered_cids),
            "compound_ids": list(covered_cids),
            "source": "chembl",
        }
    ] if covered_cids else []
    return {
        "covered": len(covered_cids),
        "no_data": len(uncovered_cids),
        "target_count": len(targets),
        "target_gene_symbols": [t["gene_symbol"] for t in targets],
        "target_compound_map": {t["gene_symbol"]: t["compound_ids"] for t in targets},
        "coverage_pct": round(len(covered_cids) / (len(covered_cids) + len(uncovered_cids)) * 100, 1)
            if (covered_cids or uncovered_cids) else 0.0,
        "targets": targets,
        "compound_sources": {cid: ["chembl"] for cid in covered_cids},
        "uncovered_compounds": [
            {"compound_id": cid, "canonical_name": f"Compound {cid}", "smiles": "CC"}
            for cid in uncovered_cids
        ],
    }


def test_merge_adds_new_target_for_uncovered_compound():
    """Importing STP results for an uncovered compound adds targets and moves it to covered."""
    from app.routers.analyses import _merge_stp_targets

    stage3 = _make_stage3(covered_cids=["cid-A"], uncovered_cids=["cid-B"])
    stp_targets = [STPTarget(uniprot_id="P00533", gene_symbol="EGFR", probability=0.45)]

    result = _merge_stp_targets(stage3, "cid-B", stp_targets)

    assert result["covered"] == 2
    assert result["no_data"] == 0
    assert len(result["uncovered_compounds"]) == 0
    gene_symbols = [t["gene_symbol"] for t in result["targets"]]
    assert "EGFR" in gene_symbols
    egfr = next(t for t in result["targets"] if t["gene_symbol"] == "EGFR")
    assert egfr["source"] == "user_provided"
    assert "cid-B" in egfr["compound_ids"]
    assert result["compound_sources"].get("cid-B") == ["user_provided"]
    assert abs(result["coverage_pct"] - 100.0) < 0.1


def test_merge_idempotent_for_already_covered_compound():
    """Importing for a compound that already has targets adds targets without changing coverage count."""
    from app.routers.analyses import _merge_stp_targets

    stage3 = _make_stage3(covered_cids=["cid-A"], uncovered_cids=["cid-B"])
    stp_targets = [STPTarget(uniprot_id="P12345", gene_symbol="BRCA1", probability=0.30)]

    result = _merge_stp_targets(stage3, "cid-A", stp_targets)

    # cid-A was already covered — covered count unchanged
    assert result["covered"] == 1
    assert result["no_data"] == 1
    gene_symbols = [t["gene_symbol"] for t in result["targets"]]
    assert "BRCA1" in gene_symbols
    assert "user_provided" in result["compound_sources"].get("cid-A", [])


def test_merge_updates_existing_target_with_new_compound():
    """If STP returns a gene already in the target list, compound_ids is extended."""
    from app.routers.analyses import _merge_stp_targets

    stage3 = _make_stage3(covered_cids=["cid-A"], uncovered_cids=["cid-B"])
    # TP53 is already in the target list (from covered_cids fixture)
    stp_targets = [STPTarget(uniprot_id="P04637", gene_symbol="TP53", probability=0.80)]

    result = _merge_stp_targets(stage3, "cid-B", stp_targets)

    tp53 = next(t for t in result["targets"] if t["gene_symbol"] == "TP53")
    assert "cid-B" in tp53["compound_ids"]
    assert "cid-A" in tp53["compound_ids"]
    assert tp53["compound_count"] == 2


def test_merge_noop_for_empty_targets():
    """Importing an empty target list does not change coverage stats or uncovered list."""
    from app.routers.analyses import _merge_stp_targets

    stage3 = _make_stage3(covered_cids=["cid-A"], uncovered_cids=["cid-B"])
    result = _merge_stp_targets(stage3, "cid-B", [])

    # Nothing should change in coverage
    assert result["covered"] == 1
    assert result["no_data"] == 1
    assert len(result["uncovered_compounds"]) == 1
    assert result["uncovered_compounds"][0]["compound_id"] == "cid-B"
    assert result["coverage_pct"] == stage3["coverage_pct"]
