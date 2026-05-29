"""Unit tests for disease_targets.utils."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/

from disease_targets.utils import (
    TARGET_NS,
    TARGET_ALIAS_NS,
    DISEASE_TARGET_NS,
    target_id,
    target_alias_id,
    disease_target_id,
    canonical_key_for_target,
    normalize_text,
    make_slug_key,
    safe_str,
)


class TestTargetId:
    def test_deterministic(self):
        assert target_id("uniprot:P31749") == target_id("uniprot:P31749")

    def test_different_keys_differ(self):
        assert target_id("uniprot:P31749") != target_id("uniprot:P12345")

    def test_returns_string(self):
        result = target_id("uniprot:P31749")
        assert isinstance(result, str)
        assert len(result) == 36  # UUID v5 format


class TestTargetAliasId:
    def test_deterministic(self):
        tid = target_id("uniprot:P31749")
        assert target_alias_id(tid, "AKT1") == target_alias_id(tid, "AKT1")

    def test_different_names_differ(self):
        tid = target_id("uniprot:P31749")
        assert target_alias_id(tid, "AKT1") != target_alias_id(tid, "AKT2")

    def test_different_targets_differ(self):
        tid1 = target_id("uniprot:P31749")
        tid2 = target_id("uniprot:P12345")
        assert target_alias_id(tid1, "AKT1") != target_alias_id(tid2, "AKT1")


class TestDiseaseTargetId:
    def test_deterministic(self):
        did = "a4fd1b5c-ac3a-594a-9023-cd30f10fb5f6"
        tid = target_id("uniprot:P31749")
        assert disease_target_id(did, tid) == disease_target_id(did, tid)

    def test_different_pairs_differ(self):
        did = "a4fd1b5c-ac3a-594a-9023-cd30f10fb5f6"
        tid1 = target_id("uniprot:P31749")
        tid2 = target_id("uniprot:P12345")
        assert disease_target_id(did, tid1) != disease_target_id(did, tid2)

    def test_different_diseases_differ(self):
        did1 = "a4fd1b5c-ac3a-594a-9023-cd30f10fb5f6"
        did2 = "d3ec7fe7-08d5-55a8-9fc3-9f4328342828"
        tid = target_id("uniprot:P31749")
        assert disease_target_id(did1, tid) != disease_target_id(did2, tid)


class TestCanonicalKeyForTarget:
    def test_uniprot_preferred(self):
        result = canonical_key_for_target("P31749", "ENSG00000145675")
        assert result == "uniprot:P31749"

    def test_ensembl_fallback_when_no_uniprot(self):
        result = canonical_key_for_target("", "ENSG00000145675")
        assert result == "ensembl:ENSG00000145675"

    def test_ensembl_fallback_when_none(self):
        result = canonical_key_for_target(None, "ENSG00000145675")
        assert result == "ensembl:ENSG00000145675"

    def test_ensembl_fallback_when_whitespace(self):
        result = canonical_key_for_target("   ", "ENSG00000145675")
        assert result == "ensembl:ENSG00000145675"

    def test_uniprot_stripped(self):
        result = canonical_key_for_target("  P31749  ", "ENSG00000145675")
        assert result == "uniprot:P31749"


class TestNormalizeText:
    def test_lowercases(self):
        assert normalize_text("AKT1 Kinase") == "akt1 kinase"

    def test_collapses_whitespace(self):
        assert normalize_text("type  2  diabetes") == "type 2 diabetes"

    def test_strips(self):
        assert normalize_text("  hello  ") == "hello"

    def test_missing_strings_to_empty(self):
        for val in ("na", "N/A", "null", "None", "-", ""):
            assert normalize_text(val) == ""

    def test_none_to_empty(self):
        assert normalize_text(None) == ""


class TestMakeSlugKey:
    def test_basic(self):
        assert make_slug_key("Type 2 Diabetes") == "type_2_diabetes"

    def test_special_chars(self):
        assert make_slug_key("non-alcoholic fatty liver disease") == "non_alcoholic_fatty_liver_disease"

    def test_empty(self):
        assert make_slug_key("") == ""

    def test_none(self):
        assert make_slug_key(None) == ""
