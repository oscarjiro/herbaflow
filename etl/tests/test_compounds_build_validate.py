"""Unit tests for the honest identity surfacing in compounds 03/05/06.

Covers the downstream half of the corroboration fix:
- 05 surfaces match_strategy / evidence_type / enrichment_confidence on compounds.csv,
  and a rejected (blank) structure falls back to the raw name_formula/name/cas identity
  via shared.identity (never a wrong InChIKey, never dropped).
- plant_compounds.source_url points at the KNApSAcK organism page.
- 06 flags a resolved structure whose formula no longer matches the raw source formula.
- 03 no longer emits the dead 'ambiguous' status and carries organism through.
"""

import csv
import importlib.util
import logging
import sys
from pathlib import Path

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))  # etl/

from shared.provenance import knapsack_organism_url  # noqa: E402


def _load(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ETL_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


build = _load("compounds_05_build", "compounds/05_build_canonical/run.py")
validate = _load("compounds_06_validate", "compounds/06_validate/run.py")
dedupe = _load("compounds_03_dedupe", "compounds/03_dedupe_candidates/run.py")
export = _load("compounds_07_export", "compounds/07_export/run.py")


# --- helpers ---------------------------------------------------------------


def _row(columns, **vals):
    r = {c: "" for c in columns}
    r.update(vals)
    return r


def _write_csv(path: Path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _settings(tmp_path: Path, **overrides):
    files = {
        "module_root": tmp_path,
        "build_out_dir": tmp_path,
        "build_log_dir": tmp_path,
        "enrich_out_dir": tmp_path,
        "dedupe_out_dir": tmp_path,
        "candidate_input_file": tmp_path / "candidates.csv",
        "candidate_members_file": tmp_path / "members.csv",
        "enrich_results_file": tmp_path / "enrich.csv",
        "enrich_member_map_file": tmp_path / "member_map.csv",
        "enrich_review_file": tmp_path / "enrich_review.csv",
        "enrich_cache_index_file": tmp_path / "cache_index_missing.csv",
        "source_name": "KNApSAcK",
        "source_url": "http://www.knapsackfamily.com",
        "batch_id": "auto",
        "run_id_prefix": "compounds",
        "timestamp_format": "%Y%m%d_%H%M%S",
        "overwrite_outputs": False,
        "auto_accept_confidence": 0.70,
        "high_confidence_threshold": 0.90,
        "medium_confidence_threshold": 0.70,
    }
    files.update(overrides)
    return build.Settings(**files)


ACCEPTED_ENRICH = dict(
    compound_candidate_id="cand1",
    candidate_key="cas::aspirin",
    candidate_status="ready",
    pubchem_cid="2244",
    inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
    molecular_formula="C9H8O4",
    molecular_weight="180.16",
    preferred_name="aspirin",
    enrichment_confidence="0.9700",
    enrichment_status="matched",
    match_strategy="cas_formula_confirmed",
    evidence_type="cas+formula",
    source_name="KNApSAcK",
)


# --- provenance URL --------------------------------------------------------


def test_knapsack_organism_url_encodes_species():
    assert knapsack_organism_url("Curcuma longa") == (
        "https://www.knapsackfamily.com/knapsack_core/result.php"
        "?sname=organism&word=Curcuma%20longa"
    )
    assert knapsack_organism_url("") is None
    assert knapsack_organism_url(None) is None


# --- 05 decision: corroborated vs raw fallback -----------------------------


def test_decide_accepted_for_corroborated_structure(tmp_path):
    candidate = {
        "inchi_key": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        "pubchem_cid": "2244",
        "chembl_id": "",
        "molecular_formula": "C9H8O4",
        "preferred_name": "aspirin",
        "iupac_name": "",
        "enrichment_status": "matched",
        "enrichment_confidence": "0.9700",
        "match_strategy": "cas_formula_confirmed",
        "evidence_type": "cas+formula",
    }
    members = [
        {
            "normalized_metabolite_name": "aspirin",
            "normalized_cas_id": "50-78-2",
            "normalized_formula": "C9H8O4",
        }
    ]
    d = build.decide_canonical_status(candidate, members, _settings(tmp_path))
    assert d["canonical_status"] == "accepted"
    assert d["canonical_strategy"] == "inchi_key"
    assert d["canonical_reason"] == "structurally_corroborated"


def test_decide_falls_back_to_cas_identity_when_structure_rejected(tmp_path):
    # 04 rejected the structure -> all structure fields blank. Must NOT become
    # unresolved: fall back to the raw CAS identity and ship as provisional.
    candidate = {
        "inchi_key": "",
        "pubchem_cid": "",
        "chembl_id": "",
        "molecular_formula": "",
        "preferred_name": "",
        "iupac_name": "",
        "enrichment_status": "review",
        "enrichment_confidence": "0.3000",
        "match_strategy": "rejected_name_only",
        "evidence_type": "name_only",
    }
    members = [
        {
            "normalized_metabolite_name": "myricetin",
            "normalized_cas_id": "529-44-2",
            "normalized_formula": "C15H10O8",
        }
    ]
    d = build.decide_canonical_status(candidate, members, _settings(tmp_path))
    assert d["canonical_status"] == "provisional"
    assert d["canonical_strategy"] == "cas_id"
    assert d["canonical_key"].startswith("cas:")
    assert d["canonical_status"] != "unresolved"


def test_decide_falls_back_to_name_formula_without_cas(tmp_path):
    candidate = {
        "inchi_key": "",
        "pubchem_cid": "",
        "chembl_id": "",
        "molecular_formula": "",
        "preferred_name": "",
        "enrichment_status": "review",
        "enrichment_confidence": "0.3000",
        "match_strategy": "rejected_formula_mismatch",
        "evidence_type": "cas_no_formula_confirm",
    }
    members = [
        {
            "normalized_metabolite_name": "myricetin",
            "normalized_cas_id": "",
            "normalized_formula": "C15H10O8",
        }
    ]
    d = build.decide_canonical_status(candidate, members, _settings(tmp_path))
    assert d["canonical_status"] == "provisional"
    assert d["canonical_strategy"] == "name_formula"
    assert d["canonical_reason"] == "name_formula_identity_no_structure"


def test_decide_unresolved_when_no_identity_at_all(tmp_path):
    candidate = {
        "inchi_key": "",
        "pubchem_cid": "",
        "chembl_id": "",
        "molecular_formula": "",
        "preferred_name": "",
        "enrichment_status": "unresolved",
        "enrichment_confidence": "0.0000",
    }
    members = [{"normalized_metabolite_name": "", "normalized_cas_id": "", "normalized_formula": ""}]
    d = build.decide_canonical_status(candidate, members, _settings(tmp_path))
    assert d["canonical_status"] == "unresolved"
    assert d["canonical_key"] == ""


# --- 05 build: provenance columns + organism source_url --------------------


def test_build_surfaces_provenance_and_organism_source_url(tmp_path):
    _write_csv(tmp_path / "enrich.csv", build.ENRICH_RESULT_COLUMNS, [_row(build.ENRICH_RESULT_COLUMNS, **ACCEPTED_ENRICH)])
    member_cols = list(build.CANDIDATE_MEMBER_COLUMNS) + ["organism"]
    _write_csv(
        tmp_path / "members.csv",
        member_cols,
        [
            _row(
                member_cols,
                compound_candidate_member_id="m1",
                compound_candidate_id="cand1",
                canonical_plant_id="plant-1",
                c_id="C0001",
                normalized_metabolite_name="aspirin",
                normalized_cas_id="50-78-2",
                normalized_formula="C9H8O4",
                organism="Curcuma longa",
                normalization_status="ready",
            )
        ],
    )
    _write_csv(tmp_path / "member_map.csv", build.ENRICH_MEMBER_MAP_COLUMNS, [])
    _write_csv(tmp_path / "enrich_review.csv", build.ENRICH_REVIEW_COLUMNS, [])

    settings = _settings(tmp_path)
    logger = logging.getLogger("test.build")
    compounds_out, _aliases, bridge_out, *_ = build.build_canonical_tables(settings, logger)

    assert len(compounds_out) == 1
    row = compounds_out[0]
    assert row["match_strategy"] == "cas_formula_confirmed"
    assert row["evidence_type"] == "cas+formula"
    assert row["enrichment_confidence"] == "0.9700"
    assert row["canonical_status"] == "accepted"
    assert row["canonical_strategy"] == "inchi_key"

    assert len(bridge_out) == 1
    assert bridge_out[0]["source_url"] == knapsack_organism_url("Curcuma longa")


def test_compounds_columns_surface_provenance_in_all_stages():
    for cols in (build.COMPOUNDS_COLUMNS, validate.COMPOUNDS_COLUMNS, export.COMPOUNDS_COLUMNS):
        for c in ("match_strategy", "evidence_type", "enrichment_confidence"):
            assert c in cols


# --- 06 formula-consistency guard ------------------------------------------


def _compound_row(**vals):
    row = {"compound_id": "cmp1", "inchi_key": "AAAAAAAAAAAAAA-BBBBBBBBBB-C", "molecular_formula": "C9H8O4"}
    row.update(vals)
    return row


def test_validate_formula_consistency_flags_mismatch():
    compound_rows = [_compound_row()]
    candidate_map_rows = [{"compound_candidate_id": "cand1", "compound_id": "cmp1"}]
    raw = {"cand1": "C10H10O2"}  # disagrees with the resolved C9H8O4
    issues = []
    stats = validate.validate_formula_consistency(
        compound_rows, candidate_map_rows, raw, "compounds.csv", issues
    )
    assert stats["formula_checked"] == 1
    assert stats["formula_mismatches"] == 1
    assert any(i.issue_type == "formula_mismatch_resolved_vs_raw" for i in issues)
    assert all(i.severity == "warning" for i in issues)


def test_validate_formula_consistency_passes_on_hill_equal_formula():
    compound_rows = [_compound_row()]
    candidate_map_rows = [{"compound_candidate_id": "cand1", "compound_id": "cmp1"}]
    raw = {"cand1": "O4C9H8"}  # same molecule, different written order
    issues = []
    stats = validate.validate_formula_consistency(
        compound_rows, candidate_map_rows, raw, "compounds.csv", issues
    )
    assert stats["formula_mismatches"] == 0
    assert issues == []


def test_validate_formula_consistency_skips_compounds_without_structure():
    compound_rows = [_compound_row(inchi_key="")]  # no resolved structure
    candidate_map_rows = [{"compound_candidate_id": "cand1", "compound_id": "cmp1"}]
    raw = {"cand1": "C10H10O2"}
    issues = []
    stats = validate.validate_formula_consistency(
        compound_rows, candidate_map_rows, raw, "compounds.csv", issues
    )
    assert stats["formula_checked"] == 0
    assert issues == []


# --- 03 dedupe: dead ambiguity removed, organism carried -------------------


def test_dedupe_member_columns_carry_organism():
    assert "organism" in dedupe.MEMBER_OUTPUT_COLUMNS


def test_dedupe_no_longer_emits_ambiguous_status():
    # Same CAS cluster with two distinct member names: the old dead check flagged
    # this 'ambiguous'; clusters are keyed on CAS so it is a normal 'ready' cluster.
    members = [
        {"normalization_status": "ready", "normalized_metabolite_key": "a", "normalized_cas_key": "50_00_0", "normalized_formula_key": "ch2o"},
        {"normalization_status": "ready", "normalized_metabolite_key": "b", "normalized_cas_key": "50_00_0", "normalized_formula_key": "ch2o"},
    ]
    status, _reason = dedupe.decide_candidate_status("cas_exact", 0.98, members, 0.70)
    assert status == "ready"


def test_dedupe_low_confidence_still_reviews():
    members = [{"normalization_status": "ready", "normalized_metabolite_key": "a"}]
    status, reason = dedupe.decide_candidate_status("name_only", 0.62, members, 0.70)
    assert status == "review"
    assert "confidence_below_threshold" in reason
