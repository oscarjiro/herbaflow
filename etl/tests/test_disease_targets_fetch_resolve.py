"""Tests for disease_targets.01_fetch xref-validated disease resolution.

The fetch step must not blindly trust the top Open Targets free-text hit. It
resolves each seed disease and accepts a hit only if its `dbXRefs` cross-reference
the seed's curated ontology id (DOID/MeSH). A hit that does not cross-reference the
seed is rejected to the review path instead of silently resolving to a wrong or
narrower disease. Ischemic Heart Disease (seed DOID_3393) must map to the concept
that carries DOID:3393, not to a narrowing top hit.
"""

import importlib.util
import logging
import sys
from pathlib import Path

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))  # etl/

_FETCH_PATH = ETL_ROOT / "disease_targets" / "01_fetch" / "run.py"
_spec = importlib.util.spec_from_file_location("dt_01_fetch", _FETCH_PATH)
fetch_mod = importlib.util.module_from_spec(_spec)
sys.modules["dt_01_fetch"] = fetch_mod
_spec.loader.exec_module(fetch_mod)

LOG = logging.getLogger("test_dt_fetch")


def _hit(hit_id, name, dbxrefs):
    return {"id": hit_id, "name": name, "object": {"dbXRefs": dbxrefs}}


class TestOntologyCurie:
    def test_doid(self):
        assert fetch_mod.ontology_curie("DOID_3393") == "DOID:3393"

    def test_doid_zero_padded(self):
        assert fetch_mod.ontology_curie("DOID_0080208") == "DOID:0080208"

    def test_mesh_uppercased(self):
        assert fetch_mod.ontology_curie("mesh_D000544") == "MESH:D000544"

    def test_empty(self):
        assert fetch_mod.ontology_curie("") == ""

    def test_none(self):
        assert fetch_mod.ontology_curie(None) == ""

    def test_missing_marker_folded(self):
        # clean_str folds na/none/- to "" -> no usable CURIE
        assert fetch_mod.ontology_curie("na") == ""

    def test_no_underscore(self):
        assert fetch_mod.ontology_curie("DOID3393") == ""


class TestSelectXrefHit:
    def test_accepts_matching_hit(self):
        hits = [_hit("MONDO_0005148", "type 2 diabetes mellitus", ["DOID:9352", "MESH:D003924"])]
        assert fetch_mod.select_xref_hit(hits, "DOID:9352")["id"] == "MONDO_0005148"

    def test_case_insensitive(self):
        hits = [_hit("MONDO_0004975", "Alzheimer disease", ["mesh:d000544"])]
        assert fetch_mod.select_xref_hit(hits, "MESH:D000544")["id"] == "MONDO_0004975"

    def test_picks_non_top_hit_that_matches(self):
        # Top hit lacks the xref; the correct concept is lower in the list.
        hits = [
            _hit("EFO_0001645", "coronary artery disease", ["EFO:0001645"]),
            _hit("MONDO_0005010", "coronary artery disorder", ["DOID:3393"]),
        ]
        assert fetch_mod.select_xref_hit(hits, "DOID:3393")["id"] == "MONDO_0005010"

    def test_rejects_when_no_hit_matches(self):
        hits = [_hit("MONDO_0024644", "myocardial ischemia", ["DOID:326"])]
        assert fetch_mod.select_xref_hit(hits, "DOID:3393") is None

    def test_empty_curie_rejects(self):
        hits = [_hit("MONDO_0005148", "t2dm", ["DOID:9352"])]
        assert fetch_mod.select_xref_hit(hits, "") is None


class TestResolveDiseaseId:
    def _patch_gql(self, monkeypatch, hits):
        monkeypatch.setattr(fetch_mod, "_gql", lambda *a, **k: {"search": {"hits": hits}})

    def test_accepts_xref_match(self, monkeypatch):
        self._patch_gql(monkeypatch, [_hit("MONDO_0005148", "t2dm", ["DOID:9352"])])
        ot_id, reason = fetch_mod.resolve_disease_id(
            "type 2 diabetes mellitus", "DOID_9352", "ep", {}, LOG
        )
        assert (ot_id, reason) == ("MONDO_0005148", "matched")

    def test_rejects_xref_mismatch(self, monkeypatch):
        # Top hit is a plausible but wrong concept without the seed's DOID.
        self._patch_gql(monkeypatch, [_hit("EFO_9999999", "wrong disease", ["DOID:0000"])])
        ot_id, reason = fetch_mod.resolve_disease_id(
            "type 2 diabetes mellitus", "DOID_9352", "ep", {}, LOG
        )
        assert ot_id is None
        assert reason == "no_xref_match:DOID:9352"

    def test_ischemic_heart_disease_maps_to_doid_3393_concept(self, monkeypatch):
        # Regression for the audit finding: IHD (seed DOID_3393) must resolve to
        # the concept carrying DOID:3393 (coronary artery disorder), NOT the
        # narrowing top free-text hit that lacks the xref.
        self._patch_gql(
            monkeypatch,
            [
                _hit("EFO_0001645", "coronary artery disease", ["EFO:0001645"]),
                _hit("MONDO_0005010", "coronary artery disorder", ["DOID:3393"]),
            ],
        )
        ot_id, reason = fetch_mod.resolve_disease_id(
            "coronary artery disease", "DOID_3393", "ep", {}, LOG
        )
        assert ot_id == "MONDO_0005010"
        assert reason == "matched"

    def test_rejects_missing_seed_ontology(self, monkeypatch):
        self._patch_gql(monkeypatch, [_hit("MONDO_0005148", "t2dm", ["DOID:9352"])])
        ot_id, reason = fetch_mod.resolve_disease_id("t2dm", "", "ep", {}, LOG)
        assert ot_id is None
        assert reason == "no_seed_ontology_id"

    def test_rejects_no_hits(self, monkeypatch):
        self._patch_gql(monkeypatch, [])
        ot_id, reason = fetch_mod.resolve_disease_id("nonsense", "DOID_9352", "ep", {}, LOG)
        assert ot_id is None
        assert reason == "no_hits"

    def test_rejects_search_failure(self, monkeypatch):
        monkeypatch.setattr(fetch_mod, "_gql", lambda *a, **k: None)
        ot_id, reason = fetch_mod.resolve_disease_id("t2dm", "DOID_9352", "ep", {}, LOG)
        assert ot_id is None
        assert reason == "search_failed"
