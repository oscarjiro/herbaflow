"""Unit tests for the corroboration-gated identity acceptance in compounds/04.

The enrichment step must accept a resolved structure as authoritative identity
ONLY when the evidence is corroborated, the decisive check being molecular
formula agreement (a correct resolution preserves the raw source formula).
These tests use hand-built hits (no network) to cover every accept/reject path
and confirm the emitted confidence is honest.
"""

import importlib.util
import sys
from pathlib import Path

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))  # etl/

from shared import identity  # noqa: E402


def _load(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ETL_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


enrich = _load("compounds_04_enrich_identity", "compounds/04_enrich/run.py")


# --- helpers ---------------------------------------------------------------


def _term(text: str, kind: str):
    return enrich.SearchTerm(text=text, kind=kind, priority=1, provenance="test")


def _hit(
    *,
    identifier: str,
    source_name: str = "PubChem",
    formula: str = "",
    preferred_name: str = "",
    synonyms=(),
    inchi_key: str = "",
    match_score: float = 0.9,
    matched_term_kind: str = "name",
):
    return enrich.SourceHit(
        source_name=source_name,
        identifier=identifier,
        source_url=f"http://example/{identifier}",
        molecular_formula=formula,
        preferred_name=preferred_name,
        synonyms=tuple(synonyms),
        inchi_key=inchi_key,
        match_score=match_score,
        matched_term_kind=matched_term_kind,
    )


ASPIRIN = {
    "representative_name": "aspirin",
    "representative_cas_id": "50-78-2",
    "representative_formula": "C9H8O4",
    "representative_mw": "180.16",
}


# --- Hill formula normalization -------------------------------------------


def test_hill_formula_normalizes_and_orders():
    assert identity.hill_formula("C9H8O4") == "C9H8O4"
    assert identity.hill_formula("O4C9H8") == "C9H8O4"
    assert identity.hill_formula(" c9 h8 o4 ") == ""  # lowercase is not a formula
    assert identity.hill_formula("H2O") == "H2O"
    assert identity.hill_formula("(CH3)2CO") == "C3H6O"


def test_formula_matches_desalts_and_rejects_mismatches():
    assert identity.formula_matches("C9H8O4", "C9H8O4") is True
    assert identity.formula_matches("C9H8O4", "C9H9O4") is False  # one H off
    # Salt/hydrate desalts to the largest organic component, so it now matches.
    assert identity.formula_matches("C9H8O4", "C9H8O4.HCl") is True
    assert identity.formula_matches("", "C9H8O4") is False


# --- Accept paths ----------------------------------------------------------


def test_cas_plus_formula_is_accepted_high_confidence():
    terms = [_term("50-78-2", "cas"), _term("aspirin", "name")]
    hit = _hit(
        identifier="2244",
        formula="C9H8O4",
        preferred_name="aspirin",
        synonyms=("50-78-2",),
        inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        match_score=0.99,
    )
    d = enrich.evaluate_identity(ASPIRIN, terms, [hit], "")
    assert d.accepted is True
    assert d.hit is hit
    assert d.strategy == "cas_formula_confirmed"
    assert d.evidence_type == "cas+formula"
    assert d.confidence == 0.97
    assert d.status == "matched"


def test_name_plus_formula_is_accepted_but_lower_confidence():
    # No CAS term; only a strong name match plus formula agreement.
    terms = [_term("aspirin", "name")]
    hit = _hit(
        identifier="2244",
        formula="C9H8O4",
        preferred_name="aspirin",
        inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        match_score=0.94,
    )
    d = enrich.evaluate_identity(ASPIRIN, terms, [hit], "")
    assert d.accepted is True
    assert d.strategy == "name_formula_confirmed"
    assert d.evidence_type == "name+formula"
    assert d.confidence == 0.90


def test_cross_source_inchikey_plus_formula_is_accepted():
    # Neither name nor CAS matches the hit, but PubChem+ChEMBL agree on the
    # InChIKey and the formula agrees -> structural corroboration.
    terms = [_term("aspirin", "name")]
    hit = _hit(
        identifier="2244",
        formula="C9H8O4",
        preferred_name="something else entirely",
        inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        match_score=0.9,
    )
    d = enrich.evaluate_identity(ASPIRIN, terms, [hit], "BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    assert d.accepted is True
    assert d.strategy == "cross_source_confirmed"
    assert d.confidence == 0.97


# --- Reject paths ----------------------------------------------------------


def test_name_only_is_rejected():
    terms = [_term("aspirin", "name")]
    hit = _hit(
        identifier="999",
        formula="C10H10O2",  # disagrees with raw C9H8O4
        preferred_name="aspirin",
        inchi_key="WRONGKEY-AAAAAAAAAA-N",
        match_score=0.94,
    )
    d = enrich.evaluate_identity(ASPIRIN, terms, [hit], "")
    assert d.accepted is False
    assert d.hit is None
    assert d.strategy == "rejected_name_only"
    assert d.evidence_type == "name_only"
    assert d.confidence == 0.30
    assert d.status == "review"


def test_formula_only_is_rejected():
    # Formula agrees but no name/CAS/structure corroboration (isomer-blind).
    terms = [_term("aspirin", "name")]
    hit = _hit(
        identifier="777",
        formula="C9H8O4",
        preferred_name="a different molecule",
        inchi_key="ISOMERKEY-BBBBBBBBBB-N",
        match_score=0.9,
    )
    d = enrich.evaluate_identity(ASPIRIN, terms, [hit], "")
    assert d.accepted is False
    assert d.strategy == "rejected_formula_only"
    assert d.evidence_type == "formula_only"


def test_molecular_weight_only_is_rejected():
    terms = [_term("180.16", "mw")]
    hit = _hit(
        identifier="555",
        formula="C30H36FN7O2",  # disagrees
        preferred_name="fluorinated drug",
        match_score=0.82,
        matched_term_kind="mw",
    )
    d = enrich.evaluate_identity(ASPIRIN, terms, [hit], "")
    assert d.accepted is False
    assert d.strategy == "rejected_mw"
    assert d.evidence_type == "mw_only"


def test_cas_match_with_formula_mismatch_is_rejected():
    # CAS appears as a synonym but the resolved formula disagrees: wrong molecule.
    terms = [_term("50-78-2", "cas")]
    hit = _hit(
        identifier="444",
        formula="C10H10O2",
        preferred_name="mislabeled record",
        synonyms=("50-78-2",),
        match_score=0.97,
    )
    d = enrich.evaluate_identity(ASPIRIN, terms, [hit], "")
    assert d.accepted is False
    assert d.strategy == "rejected_formula_mismatch"


def test_ambiguous_tie_between_distinct_structures_is_rejected():
    terms = [_term("aspirin", "name")]
    hit_a = _hit(
        identifier="A",
        formula="C19H20O4",
        preferred_name="asiaticin",
        inchi_key="AAAAAAAAAAAAAA-AAAAAAAAAA-N",
        match_score=0.94,
    )
    hit_b = _hit(
        identifier="B",
        source_name="ChEMBL",
        formula="C19H20O4",
        preferred_name="artoindonesianin f",
        inchi_key="BBBBBBBBBBBBBB-BBBBBBBBBB-N",
        match_score=0.93,
    )
    # Candidate whose raw formula does NOT agree, so neither hit is corroborated.
    candidate = {**ASPIRIN, "representative_formula": "C99H99O99"}
    d = enrich.evaluate_identity(candidate, terms, [hit_a, hit_b], "")
    assert d.accepted is False
    assert d.strategy == "rejected_ambiguous_tie"
    assert d.count == "2"


def test_no_hits_is_unresolved():
    d = enrich.evaluate_identity(ASPIRIN, [_term("aspirin", "name")], [], "")
    assert d.accepted is False
    assert d.strategy == ""
    assert d.status == "unresolved"
    assert d.evidence_type == "none"


def test_corroborated_hit_wins_even_when_not_top_scored():
    # Top-scored hit is a wrong-formula name collision; a lower-scored hit is
    # CAS+formula corroborated. The corroborated one must be chosen.
    terms = [_term("50-78-2", "cas"), _term("aspirin", "name")]
    wrong = _hit(
        identifier="WRONG",
        formula="C10H10O2",
        preferred_name="aspirin",
        match_score=0.99,
    )
    right = _hit(
        identifier="RIGHT",
        formula="C9H8O4",
        preferred_name="acetylsalicylic acid",
        synonyms=("50-78-2",),
        inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        match_score=0.9,
    )
    d = enrich.evaluate_identity(ASPIRIN, terms, [wrong, right], "")
    assert d.accepted is True
    assert d.hit is right
    assert d.strategy == "cas_formula_confirmed"


# --- Fetch early-exit predicate -------------------------------------------
#
# _hit_accept_ready gates the fetch loop's early-exit. It must fire for exactly
# the single-source accept paths (CAS or name signal WITH formula agreement) so
# the loop stops only when the accept decision is already settled, and never for
# a hit that would ultimately be rejected.


def test_accept_ready_true_for_cas_plus_formula():
    terms = [_term("50-78-2", "cas"), _term("aspirin", "name")]
    hit = _hit(
        identifier="2244",
        formula="C9H8O4",
        preferred_name="aspirin",
        synonyms=("50-78-2",),
        match_score=0.99,
    )
    assert enrich._hit_accept_ready(ASPIRIN, terms, hit) is True


def test_accept_ready_true_for_name_plus_formula():
    terms = [_term("aspirin", "name")]
    hit = _hit(identifier="2244", formula="C9H8O4", preferred_name="aspirin")
    assert enrich._hit_accept_ready(ASPIRIN, terms, hit) is True


def test_accept_ready_false_when_formula_disagrees():
    # Strong name match but wrong formula -> not accept-ready (would be rejected).
    terms = [_term("aspirin", "name")]
    hit = _hit(identifier="X", formula="C10H10O2", preferred_name="aspirin")
    assert enrich._hit_accept_ready(ASPIRIN, terms, hit) is False


def test_accept_ready_false_for_formula_only():
    # Formula agrees but no CAS/name signal -> not accept-ready (formula-only is
    # rejected, and is never searched anyway).
    terms = [_term("aspirin", "name")]
    hit = _hit(identifier="X", formula="C9H8O4", preferred_name="something else")
    assert enrich._hit_accept_ready(ASPIRIN, terms, hit) is False


def test_search_functions_skip_formula_and_mw_terms(monkeypatch):
    # The fetch path must never issue a formula or molecular-weight search: build
    # a term list of every kind and assert only CAS/name terms reach the URL
    # builder. No network: cached_get_json is stubbed to a not-ok record.
    terms = [
        _term("50-78-2", "cas"),
        _term("aspirin", "name"),
        _term("C9H8O4", "formula"),
        _term("180.16", "mw"),
    ]
    searched = []

    def fake_get(url, *args, **kwargs):
        searched.append(url)
        return {"ok": False, "status_code": 404, "error": "", "response_json": {}}, False

    monkeypatch.setattr(enrich, "cached_get_json", fake_get)

    class _S:
        pubchem_cfg = {"base_url": "https://pubchem.example/rest/pug"}
        chembl_cfg = {"base_url": "https://chembl.example/data"}
        cache_root = Path(".")
        cache_responses = False
        timeout_seconds = 1
        max_retries = 0
        request_delay_seconds = 0.0
        source_name = "KNApSAcK"
        max_terms_per_source = 8
        max_pubchem_cids = 10
        max_chembl_hits = 10
        max_requests_per_second = 5.0
        max_requests_per_minute = 400

    import logging

    log = logging.getLogger("test")
    enrich.search_pubchem(ASPIRIN, terms, _S(), log, Path("."))
    enrich.search_chembl(ASPIRIN, terms, _S(), log, Path("."))
    # Neither a /formula/ search, the formula term text, nor the MW value appears.
    assert not any("/formula/" in u for u in searched)
    assert not any("C9H8O4" in u for u in searched)
    assert not any("180.16" in u for u in searched)
    # CAS and name terms are searched on both sources.
    assert any("50-78-2" in u for u in searched)
    assert any("aspirin" in u for u in searched)


# --- Per-candidate request budget -----------------------------------------


def test_request_budget_charge_and_exhaust():
    budget = enrich.RequestBudget(3)
    assert budget.exhausted() is False
    budget.charge()
    budget.charge()
    assert budget.exhausted() is False
    budget.charge()
    assert budget.exhausted() is True
    # A budget of 0 disables the cap (never exhausts).
    unlimited = enrich.RequestBudget(0)
    for _ in range(50):
        unlimited.charge()
    assert unlimited.exhausted() is False


def test_budget_stops_non_corroborating_search(monkeypatch):
    # A candidate whose searches never corroborate must stop after `budget`
    # requests instead of exhausting every CAS/name term. Each not-ok search
    # charges exactly one request (no CIDs to expand), so with 6 name terms and
    # a budget of 3 only 3 requests are ever issued.
    terms = [_term(f"name{i}", "name") for i in range(6)]
    searched = []

    def fake_get(url, *args, **kwargs):
        searched.append(url)
        return {"ok": False, "status_code": 404, "error": "", "response_json": {}}, False

    monkeypatch.setattr(enrich, "cached_get_json", fake_get)

    class _S:
        pubchem_cfg = {"base_url": "https://pubchem.example/rest/pug"}
        chembl_cfg = {"base_url": "https://chembl.example/data"}
        cache_root = Path(".")
        cache_responses = False
        timeout_seconds = 1
        max_retries = 0
        request_delay_seconds = 0.0
        source_name = "KNApSAcK"
        max_terms_per_source = 8
        max_pubchem_cids = 10
        max_chembl_hits = 10
        max_requests_per_second = 5.0
        max_requests_per_minute = 400

    import logging

    log = logging.getLogger("test")
    budget = enrich.RequestBudget(3)
    enrich.search_pubchem(ASPIRIN, terms, _S(), log, Path("."), budget=budget)
    assert len(searched) == 3
    assert budget.exhausted() is True
