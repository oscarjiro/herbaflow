"""Regression tests for assorted ETL correctness fixes.

Covers:
- diseases/03_build_canonical `_split_multivalue` returns [] (not "") on empty
  input, matching its `-> list[str]` contract.
- compounds/06_validate `load_optional_plant_ids` does not raise
  UnboundLocalError when the optional plant export file is missing.
- knapsack/main boolean CLI flags parse to real booleans and support
  the --no-<flag> form (BooleanOptionalAction), so "--resume False" can no
  longer store a truthy string.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))  # etl/


def _load(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ETL_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass introspection (KW_ONLY lookup via
    # sys.modules[cls.__module__]) resolves while the module body runs.
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


diseases_canonical = _load(
    "diseases_03_build_canonical", "diseases/03_build_canonical/run.py"
)
compounds_validate = _load(
    "compounds_06_validate", "compounds/06_validate/run.py"
)
knapsack_main = _load("knapsack_main", "knapsack/main.py")


class TestSplitMultivalue:
    def test_empty_returns_empty_list(self):
        assert diseases_canonical._split_multivalue("") == []

    def test_none_returns_empty_list(self):
        assert diseases_canonical._split_multivalue(None) == []

    def test_whitespace_returns_empty_list(self):
        assert diseases_canonical._split_multivalue("   ") == []

    def test_single_value(self):
        assert diseases_canonical._split_multivalue("foo") == ["foo"]

    def test_multivalue_split(self):
        result = diseases_canonical._split_multivalue("a; b, c")
        assert result == ["a", "b", "c"]


class TestLoadOptionalPlantIds:
    def test_missing_plant_export_does_not_raise(self, tmp_path):
        settings = SimpleNamespace(
            plant_export_csv=tmp_path / "does_not_exist.csv"
        )
        logger = logging.getLogger("test_load_optional_plant_ids")
        plant_ids, loaded = compounds_validate.load_optional_plant_ids(
            settings, logger
        )
        assert plant_ids == set()
        assert loaded is False

    def test_none_plant_export_does_not_raise(self, tmp_path):
        settings = SimpleNamespace(plant_export_csv=None)
        logger = logging.getLogger("test_load_optional_plant_ids")
        plant_ids, loaded = compounds_validate.load_optional_plant_ids(
            settings, logger
        )
        assert plant_ids == set()
        assert loaded is False

    def test_present_plant_export_loads_ids(self, tmp_path):
        export = tmp_path / "plants.csv"
        export.write_text("plant_id\np1\np2\n\n", encoding="utf-8")
        settings = SimpleNamespace(plant_export_csv=export)
        logger = logging.getLogger("test_load_optional_plant_ids")
        plant_ids, loaded = compounds_validate.load_optional_plant_ids(
            settings, logger
        )
        assert plant_ids == {"p1", "p2"}
        assert loaded is True


class TestKnapsackBooleanFlags:
    def _parse(self, argv):
        old = sys.argv
        try:
            sys.argv = ["main.py"] + argv
            return knapsack_main.parse_args()
        finally:
            sys.argv = old

    def test_defaults(self):
        args = self._parse([])
        assert args.resume is False
        assert args.require_detail_url is True

    def test_resume_flag(self):
        args = self._parse(["--resume"])
        assert args.resume is True

    def test_no_resume_flag(self):
        args = self._parse(["--no-resume"])
        assert args.resume is False

    def test_no_require_detail_url(self):
        args = self._parse(["--no-require-detail-url"])
        assert args.require_detail_url is False

    def test_flags_are_real_booleans(self):
        args = self._parse(["--resume"])
        assert isinstance(args.resume, bool)
        assert isinstance(args.require_detail_url, bool)


import uuid

import pandas as pd


def _extract_list_literal(text, name):
    import re
    start = text.index(f"{name} = [")
    end = text.index("]", start)
    return set(re.findall(r'"([^"]+)"', text[start:end]))


def test_plants_loaded_export_columns_have_no_dead_columns():
    import pathlib
    text = pathlib.Path("etl/plants/06_export/run.py").read_text(encoding="utf-8")
    plants = _extract_list_literal(text, "PLANTS_SCHEMA_COLUMNS")
    aliases = _extract_list_literal(text, "ALIASES_SCHEMA_COLUMNS")
    assert {"source_batch_id", "confidence"}.isdisjoint(plants), f"plants still: {plants}"
    assert {"source_batch_id"}.isdisjoint(aliases), f"aliases still: {aliases}"


def test_compounds_loaded_export_columns_have_no_dead_columns():
    import pathlib
    # evidence_type is intentionally NOT dead: it is a first-class compound
    # identity-evidence column surfaced on compounds.csv.
    dead = {"source_batch_id", "confidence",
            "source_plant_raw_id", "source_compound_raw_id"}
    text = pathlib.Path("etl/compounds/07_export/run.py").read_text(encoding="utf-8")
    for const in ("COMPOUNDS_COLUMNS", "ALIASES_COLUMNS", "PLANT_COMPOUNDS_COLUMNS"):
        block = _extract_list_literal(text, const)
        assert dead.isdisjoint(block), f"{const} still lists {dead & block}"


def test_diseases_loaded_export_columns_have_no_dead_columns():
    import pathlib
    dead = {"source_batch_id", "confidence"}
    text = pathlib.Path("etl/diseases/03_build_canonical/run.py").read_text(encoding="utf-8")
    for const in ("DISEASE_OUTPUT_COLUMNS", "ALIAS_OUTPUT_COLUMNS"):
        block = _extract_list_literal(text, const)
        assert dead.isdisjoint(block), f"{const} still lists {dead & block}"


def test_disease_targets_build_emits_no_dead_columns():
    import pathlib
    text = pathlib.Path("etl/disease_targets/03_build_canonical/run.py").read_text(encoding="utf-8")
    assert '"source_batch_id":' not in text, "disease_targets build still emits source_batch_id"
    assert '"confidence":' not in text, "disease_targets build still emits confidence"

from shared.identity import PLANT_ALIAS_NS

plants_canonical = _load(
    "plants_04_build_canonical_part2", "plants/04_build_canonical/run_part2.py"
)


class TestPlantAliasSlugCollapse:
    """alias_id = uuid5(PLANT_ALIAS_NS, '{plant_id}:{alias_key}') excludes
    alias_type, so two alias candidates that fold to the same slug but carry
    different alias_types MUST collapse to a single row per (plant_id, alias_key)
    — otherwise they would emit duplicate alias_id rows and break
    UNIQUE(plant_id, alias_key)."""

    def test_same_slug_different_alias_type_collapses_to_one_row(self):
        # Two input rows for the same accepted species. Row 1 contributes
        # "Curcuma longa" as exact_scraped_spelling; row 2's matched_name
        # "Curcuma  longa" folds to the SAME slug but would be a synonym_variant.
        group = pd.DataFrame(
            [
                {
                    "canonical_scientific_name": "Curcuma zedoaria",
                    "authorship": "Rosc.",
                    "gbif_accepted_usage_key": "3190652",
                    "gbif_usage_key": "3190652",
                    "original_species_name": "Curcuma longa",
                    "matched_name": "",
                    "confidence": "0.99",
                },
                {
                    "canonical_scientific_name": "Curcuma zedoaria",
                    "authorship": "Rosc.",
                    "gbif_accepted_usage_key": "3190652",
                    "gbif_usage_key": "3190652",
                    "original_species_name": "",
                    "matched_name": "Curcuma  longa",
                    "confidence": "0.50",
                },
            ]
        )

        plant_row, aliases = plants_canonical.canonicalize_group(
            group, "KNApSAcK World"
        )

        pid = plant_row["plant_id"]
        rows = [a for a in aliases if a["alias_key"] == "curcuma_longa"]
        assert len(rows) == 1, f"expected one row for slug, got {rows}"

        only = rows[0]
        expected_alias_id = str(uuid.uuid5(PLANT_ALIAS_NS, f"{pid}:curcuma_longa"))
        assert only["alias_id"] == expected_alias_id
        # First-seen wins on the priority tie (plant alias types absent from
        # ALIAS_PRIORITY), so exact_scraped_spelling is the deterministic winner.
        assert only["alias_type"] == "exact_scraped_spelling"

        # No duplicate alias_id anywhere in the output.
        ids = [a["alias_id"] for a in aliases]
        assert len(ids) == len(set(ids))

    def test_plant_id_and_canonical_key_use_gbif(self):
        group = pd.DataFrame(
            [
                {
                    "canonical_scientific_name": "Curcuma longa",
                    "authorship": "L.",
                    "gbif_accepted_usage_key": "3190652",
                    "gbif_usage_key": "3190652",
                    "original_species_name": "Curcuma longa",
                    "confidence": "0.99",
                }
            ]
        )
        plant_row, _ = plants_canonical.canonicalize_group(group, "KNApSAcK World")
        assert plant_row["canonical_key"] == "gbif:3190652"
        assert plant_row["plant_id"] == plants_canonical.make_plant_id(
            "3190652", "Curcuma longa L."
        )


compounds_canonical = _load(
    "compounds_05_build_canonical", "compounds/05_build_canonical/run.py"
)


def test_collect_alias_items_drops_dead_source_batch_id():
    """Alias rows never reach the loaded CSV with a source_batch_id:
    ALIASES_COLUMNS omits it and the dedup pass rebuilds each row without it.
    The collect_alias_items plumbing that threads source_batch_id is therefore
    dead — guard that the parameter and the schema constant stay free of it so
    it cannot silently rot back in."""
    import inspect

    params = inspect.signature(
        compounds_canonical.collect_alias_items
    ).parameters
    assert "source_batch_id" not in params, (
        f"collect_alias_items still threads source_batch_id: {list(params)}"
    )
    assert "source_batch_id" not in set(compounds_canonical.ALIASES_COLUMNS)


class TestCompoundsOrchestratorBuildCmd:
    """The compounds orchestrator must invoke every stage with no path flags.

    Each stage script resolves its inputs and outputs from compounds/settings.yml
    (via load_settings) and its argparse accepts only --settings plus optional
    --input overrides. If main.py passes legacy --input/--plants-csv/--output-dir/
    --input-dir flags, argparse rejects them (exit 2) and the pipeline halts at
    the first offending stage. Guard that build_cmd emits a bare [python, script]
    command for every stage so the stale flags cannot rot back in.
    """

    def test_build_cmd_emits_no_path_flags(self):
        compounds_main = _load("compounds_main", "compounds/main.py")
        for step in compounds_main.STAGE_KEYS:
            cmd = compounds_main.build_cmd(step)
            assert cmd == [
                sys.executable,
                str(ETL_ROOT / compounds_main.STAGE_SCRIPTS[step]),
            ], f"stage {step} produced unexpected args: {cmd}"


compounds_enrich = _load("compounds_04_enrich", "compounds/04_enrich/run.py")


class TestPubChemSmilesKeyDrift:
    """PubChem PUG-REST renamed its SMILES properties in 2025:
    CanonicalSMILES -> ConnectivitySMILES and IsomericSMILES -> SMILES. The
    server accepts the legacy names in the request (HTTP 200) but returns the
    payload under the NEW keys, so a parser that only reads the legacy keys gets
    an empty SMILES for every fresh fetch. The properties parser must read the
    current keys, and the request URL must ask for them; legacy keys stay as a
    fallback so pre-rename cached responses still parse.
    """

    def test_new_keys_extracted(self):
        prop = {
            "CID": 2244,
            "SMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
            "ConnectivitySMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
            "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            "MolecularFormula": "C9H8O4",
            "MolecularWeight": "180.16",
            "IUPACName": "2-acetyloxybenzoic acid",
            "Title": "Aspirin",
        }
        hit = compounds_enrich.pubchem_hit_from_properties(
            "2244", prop, [], 1, "http://example/2244"
        )
        assert hit.smiles == "CC(=O)OC1=CC=CC=C1C(=O)O"
        assert hit.inchi_key == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"

    def test_legacy_keys_still_extracted(self):
        # Pre-rename cached responses carry the old key names — must still parse.
        prop = {
            "CID": 2244,
            "CanonicalSMILES": "OLD_CANONICAL",
            "IsomericSMILES": "OLD_ISOMERIC",
            "InChIKey": "K",
        }
        hit = compounds_enrich.pubchem_hit_from_properties(
            "2244", prop, [], 1, "http://example/2244"
        )
        assert hit.smiles == "OLD_CANONICAL"

    def test_properties_url_requests_current_smiles_names(self):
        url = compounds_enrich.pubchem_properties_url(
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug", "2244"
        )
        assert "ConnectivitySMILES" in url
        assert "/property/" in url and "SMILES" in url
        assert "CanonicalSMILES" not in url
        assert "IsomericSMILES" not in url
