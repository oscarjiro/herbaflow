"""Unit tests for the KNApSAcK source-structure anchor in compounds/04.

The enrichment step now anchors compound identity on KNApSAcK's own published
structure: when a candidate member's KNApSAcK structure formula corroborates the
raw representative formula, that structure IS accepted as the identity and the
external PubChem/ChEMBL identity search is skipped entirely. These tests drive
`enrich_candidate` with a stubbed `structure_by_cid` and a spied-on
`search_pubchem` to prove the anchor wins and the search is never consulted, and
that a disagreeing formula falls through to the unchanged search path.
"""

import importlib.util
import logging
import sys
from pathlib import Path

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))  # etl/

from shared import identity  # noqa: E402,F401


def _load(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ETL_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


enrich = _load("compounds_04_enrich_knapsack", "compounds/04_enrich/run.py")

LOG = logging.getLogger("test.knapsack")

ASPIRIN_INCHIKEY = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
ASPIRIN_SMILES = "CC(=O)OC1=CC=CC=C1C(=O)O"


def _settings(tmp_path: Path):
    return enrich.Settings(
        module_root=ETL_ROOT / "compounds",
        dedupe_out_dir=tmp_path / "dedupe",
        enrich_out_dir=tmp_path / "enrich",
        enrich_log_dir=tmp_path / "enrich" / "logs",
        cache_root=tmp_path / "cache",
        candidate_input_file=tmp_path / "candidates.csv",
        member_input_file=tmp_path / "members.csv",
        review_input_file=tmp_path / "review.csv",
        source_name="KNApSAcK",
        source_url="http://www.knapsackfamily.com/",
        batch_id="test-batch",
        run_id_prefix="compounds",
        timestamp_format="%Y%m%d_%H%M%S",
        overwrite_outputs=False,
        write_summary_json=False,
        min_auto_accept_confidence=0.70,
        high_confidence_threshold=0.90,
        medium_confidence_threshold=0.70,
        pubchem_cfg={"base_url": "https://pubchem.example/rest/pug"},
        chembl_cfg={"base_url": "https://chembl.example/data"},
        cache_responses=True,
        request_delay_seconds=0.0,
        max_retries=0,
        timeout_seconds=1,
        max_pubchem_cids=10,
        max_chembl_hits=10,
        max_terms_per_source=8,
        max_requests_per_second=5.0,
        max_requests_per_minute=400,
        max_requests_per_candidate=8,
        enrich_limit=0,
    )


def _candidate(formula: str):
    return {
        "compound_candidate_id": "cand-1",
        "candidate_key": "aspirin|c9h8o4",
        "candidate_status": "ready",
        "search_priority": "1",
        "representative_name": "aspirin",
        "representative_cas_id": "50-78-2",
        "representative_formula": formula,
        "representative_mw": "180.16",
        "source_url": "http://www.knapsackfamily.com/knapsack_core/information.php?word=C001",
        "review_reason": "",
    }


def _members(c_id: str = "C001"):
    return [
        {
            "compound_candidate_member_id": "m-1",
            "compound_candidate_id": "cand-1",
            "c_id": c_id,
            "cas_id": "50-78-2",
            "metabolite": "aspirin",
            "normalized_metabolite_name": "aspirin",
            "normalized_cas_id": "50-78-2",
            "normalized_formula": "C9H8O4",
        }
    ]


def _stub_adme(monkeypatch, *, qed="0.55", chembl_np="", ro5="0", is_pains=False):
    """Stub every property call so tests are hermetic (no RDKit model load, no
    network to ChEMBL) while still proving the anchor SOURCES ADME from them."""
    monkeypatch.setattr(
        enrich,
        "rdkit_descriptors",
        lambda smiles: {
            "logp": "1.31",
            "hbond_donors": "1",
            "hbond_acceptors": "4",
            "tpsa": "63.6",
            "rotatable_bonds": "3",
            "molecular_weight": "180.159",
        },
    )
    monkeypatch.setattr(enrich, "np_likeness", lambda smiles: "0.42")
    monkeypatch.setattr(enrich, "check_pains", lambda smiles: is_pains)
    monkeypatch.setattr(
        enrich,
        "chembl_detail_by_inchikey",
        lambda inchi_key, cache_dir: {
            "qed_score": qed,
            "np_likeness_score": chembl_np,
            "num_ro5_violations": ro5,
        },
    )


def _spy_search(monkeypatch):
    calls = {"pubchem": 0, "chembl": 0}

    def _pubchem(*args, **kwargs):
        calls["pubchem"] += 1
        return [], {"source": "PubChem", "requests": []}

    def _chembl(*args, **kwargs):
        calls["chembl"] += 1
        return [], {"source": "ChEMBL", "requests": []}

    monkeypatch.setattr(enrich, "search_pubchem", _pubchem)
    monkeypatch.setattr(enrich, "search_chembl", _chembl)
    return calls


# --- Accept path -----------------------------------------------------------


def test_knapsack_structure_accepted_when_formula_agrees(tmp_path, monkeypatch):
    monkeypatch.setattr(
        enrich,
        "structure_by_cid",
        {"C001": (ASPIRIN_INCHIKEY, ASPIRIN_SMILES, "C9H8O4")},
    )
    _stub_adme(monkeypatch, chembl_np="")
    calls = _spy_search(monkeypatch)

    result, member_map, cache_index, cache_hit = enrich.enrich_candidate(
        _candidate("C9H8O4"), _members(), None, _settings(tmp_path), LOG
    )

    # The KNApSAcK structure was accepted as the identity...
    assert result["match_strategy"] == "knapsack_source_confirmed"
    assert result["evidence_type"] == "knapsack+formula"
    assert result["enrichment_status"] == "matched"
    assert result["enrichment_confidence"] == "0.9700"
    assert result["inchi_key"] == ASPIRIN_INCHIKEY
    assert result["smiles"] == ASPIRIN_SMILES
    assert result["molecular_formula"] == "C9H8O4"
    assert result["match_rank"] == "1"
    assert result["match_count"] == "1"
    # ...ADME computed inline from the accepted SMILES / InChIKey...
    assert result["logp"] == "1.31"
    assert result["molecular_weight"] == "180.159"
    assert result["qed_score"] == "0.55"
    assert result["num_ro5_violations"] == "0"
    assert result["np_likeness_score"] == "0.42"  # ChEMBL blank -> RDKit NP fallback
    assert result["is_pains_positive"] == "false"
    assert result["lipinski_source"] == "rdkit_computed"
    # ...and the external identity search was NEVER consulted.
    assert calls["pubchem"] == 0
    assert calls["chembl"] == 0
    assert cache_hit is False
    # member map carries the accepted structure
    assert member_map[0]["chosen_inchi_key"] == ASPIRIN_INCHIKEY


def test_np_likeness_prefers_chembl_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(
        enrich,
        "structure_by_cid",
        {"C001": (ASPIRIN_INCHIKEY, ASPIRIN_SMILES, "C9H8O4")},
    )
    _stub_adme(monkeypatch, chembl_np="0.12")
    _spy_search(monkeypatch)

    result, *_ = enrich.enrich_candidate(
        _candidate("C9H8O4"), _members(), None, _settings(tmp_path), LOG
    )
    assert result["np_likeness_score"] == "0.12"  # ChEMBL value wins over RDKit


def test_charged_knapsack_formula_corroborates(tmp_path, monkeypatch):
    # Task-1 charge-aware matching: a raw cationic formula matches the same
    # published cationic formula and is accepted.
    monkeypatch.setattr(
        enrich,
        "structure_by_cid",
        {"C001": ("PELLETIER-KEYXXXXXXXXXX-N", "c1cc[o+]cc1", "C15H11O6+")},
    )
    _stub_adme(monkeypatch)
    calls = _spy_search(monkeypatch)

    result, *_ = enrich.enrich_candidate(
        _candidate("C15H11O6+"), _members(), None, _settings(tmp_path), LOG
    )
    assert result["match_strategy"] == "knapsack_source_confirmed"
    assert result["inchi_key"] == "PELLETIER-KEYXXXXXXXXXX-N"
    assert result["molecular_formula"] == "C15H11O6+"  # stored as published
    assert calls["pubchem"] == 0


# --- Fall-through path ------------------------------------------------------


def test_falls_through_when_knapsack_formula_disagrees(tmp_path, monkeypatch):
    # KNApSAcK structure exists but its formula disagrees with the raw formula:
    # the anchor must not fire; the existing search path runs unchanged.
    monkeypatch.setattr(
        enrich,
        "structure_by_cid",
        {"C001": ("WRONGKEY-AAAAAAAAAA-N", "C1=CC=CC=C1", "C10H10")},
    )
    calls = _spy_search(monkeypatch)

    result, _member_map, _cache_index, _cache_hit = enrich.enrich_candidate(
        _candidate("C19H24O6"), _members(), None, _settings(tmp_path), LOG
    )
    # Search consulted; no hits -> unresolved (structure fields blank).
    assert calls["pubchem"] == 1
    assert result["match_strategy"] == ""
    assert result["enrichment_status"] == "unresolved"
    assert result["inchi_key"] == ""


def test_falls_through_when_no_knapsack_structure(tmp_path, monkeypatch):
    # Empty map (the current on-disk state, pre re-scrape): every candidate
    # falls through to the search path.
    monkeypatch.setattr(enrich, "structure_by_cid", {})
    calls = _spy_search(monkeypatch)

    result, *_ = enrich.enrich_candidate(
        _candidate("C9H8O4"), _members(), None, _settings(tmp_path), LOG
    )
    assert calls["pubchem"] == 1
    assert result["match_strategy"] == ""


# --- Opportunistic disagreement safety flag --------------------------------


def test_disagreement_flag_when_cached_external_key_differs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        enrich,
        "structure_by_cid",
        {"C001": (ASPIRIN_INCHIKEY, ASPIRIN_SMILES, "C9H8O4")},
    )
    _stub_adme(monkeypatch)
    _spy_search(monkeypatch)
    # A previously cached external InChIKey that disagrees with KNApSAcK's.
    monkeypatch.setattr(
        enrich,
        "_cached_external_inchikeys",
        lambda candidate, terms, settings, logger: {"DIFFERENTKEY-ZZZZZZZZZZ-N"},
    )

    result, *_ = enrich.enrich_candidate(
        _candidate("C9H8O4"), _members(), None, _settings(tmp_path), LOG
    )
    # KNApSAcK's structure is still accepted (never overridden)...
    assert result["inchi_key"] == ASPIRIN_INCHIKEY
    assert result["match_strategy"] == "knapsack_source_confirmed"
    # ...but the disagreement is surfaced in match_reason.
    assert "knapsack_vs_external_disagreement" in result["match_reason"]


def test_no_disagreement_flag_when_external_key_agrees(tmp_path, monkeypatch):
    monkeypatch.setattr(
        enrich,
        "structure_by_cid",
        {"C001": (ASPIRIN_INCHIKEY, ASPIRIN_SMILES, "C9H8O4")},
    )
    _stub_adme(monkeypatch)
    _spy_search(monkeypatch)
    monkeypatch.setattr(
        enrich,
        "_cached_external_inchikeys",
        lambda candidate, terms, settings, logger: {ASPIRIN_INCHIKEY},
    )
    result, *_ = enrich.enrich_candidate(
        _candidate("C9H8O4"), _members(), None, _settings(tmp_path), LOG
    )
    assert "knapsack_vs_external_disagreement" not in result["match_reason"]


# --- Structure-map loader ---------------------------------------------------


def test_load_structure_by_cid_defensive_on_missing_columns(tmp_path):
    # The current on-disk CSV lacks the knapsack_* columns; the loader must
    # yield an empty map, not raise a KeyError.
    csv_path = tmp_path / "plants_compounds.csv"
    csv_path.write_text(
        "plant_id,c_id,cas_id,metabolite,molecular_formula,mw,organism\n"
        "p1,C001,50-78-2,aspirin,C9H8O4,180.16,Some plant\n",
        encoding="utf-8-sig",
    )
    assert enrich.load_structure_by_cid(csv_path) == {}


def test_load_structure_by_cid_reads_populated_columns(tmp_path):
    csv_path = tmp_path / "plants_compounds.csv"
    csv_path.write_text(
        "plant_id,c_id,metabolite,molecular_formula,mw,organism,"
        "knapsack_inchikey,knapsack_smiles,knapsack_formula\n"
        "p1,C001,aspirin,C9H8O4,180.16,Some plant,"
        f"{ASPIRIN_INCHIKEY},{ASPIRIN_SMILES},C9H8O4\n"
        "p2,C002,noketone,C1,1,Other plant,,,\n",  # blank inchikey -> dropped
        encoding="utf-8-sig",
    )
    mapping = enrich.load_structure_by_cid(csv_path)
    assert mapping == {"C001": (ASPIRIN_INCHIKEY, ASPIRIN_SMILES, "C9H8O4")}


def test_load_structure_by_cid_missing_file_returns_empty(tmp_path):
    assert enrich.load_structure_by_cid(tmp_path / "does_not_exist.csv") == {}
