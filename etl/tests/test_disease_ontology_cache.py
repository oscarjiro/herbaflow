import importlib.util
import sys
from pathlib import Path

import pandas as pd

ETL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL))

spec = importlib.util.spec_from_file_location(
    "map_ontology_run", ETL / "diseases" / "02_map_ontology" / "run.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_build_cache_row_persists_synonyms_and_description():
    mapping = {
        "ontology_id": "DOID_9352",
        "ontology_source": "Disease Ontology",
        "standardized_name": "type 2 diabetes mellitus",
        "ontology_description": "A diabetes mellitus that ...",
        "ontology_synonyms": "NIDDM; type 2 diabetes; adult-onset diabetes",
        "ontology_confidence": 0.9,
        "ontology_match_method": "online_exact",
    }
    row = mod._build_cache_row(
        "type_2_diabetes_mellitus", "type_2_diabetes_mellitus", mapping
    )
    assert row["ontology_synonyms"] == "NIDDM; type 2 diabetes; adult-onset diabetes"
    assert row["ontology_description"].startswith("A diabetes mellitus")
    assert row["standardized_name"] == "type 2 diabetes mellitus"


def test_cache_hit_returns_synonyms_and_label():
    cache_df = pd.DataFrame(
        [
            {
                "disease_key": "type_2_diabetes_mellitus",
                "query_key": "type_2_diabetes_mellitus",
                "ontology_id": "DOID_9352",
                "ontology_source": "Disease Ontology",
                "standardized_name": "type 2 diabetes mellitus",
                "ontology_description": "A diabetes mellitus that ...",
                "ontology_synonyms": "NIDDM; type 2 diabetes",
                "ontology_confidence": 0.9,
                "ontology_match_method": "online_exact",
                "retrieved_at": "2026-05-06T00:00:00+00:00",
            }
        ]
    )
    hit = mod._lookup_cache(
        cache_df,
        "type_2_diabetes_mellitus",
        "type_2_diabetes_mellitus",
        ["Disease Ontology"],
    )
    assert hit is not None
    assert hit.get("ontology_synonyms") == "NIDDM; type 2 diabetes"
    assert hit.get("standardized_name") == "type 2 diabetes mellitus"
