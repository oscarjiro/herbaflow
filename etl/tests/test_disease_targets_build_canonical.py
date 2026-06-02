"""Tests for disease_targets.03_build_canonical.

Provenance contract: the canonical CSVs must carry a ``source_name`` column
(the key the loader's ``resolve_src`` reads), holding the source display name
``OpenTargets`` — a real row in ``source_systems`` (supabase/seed.sql). The old
``source_id`` column name caused the loader to write null source FKs.
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ETL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_ROOT))  # etl/

_BC_PATH = ETL_ROOT / "disease_targets" / "03_build_canonical" / "run.py"
_spec = importlib.util.spec_from_file_location("dt_03_build_canonical", _BC_PATH)
bc = importlib.util.module_from_spec(_spec)
sys.modules["dt_03_build_canonical"] = bc
_spec.loader.exec_module(bc)


def _cfg():
    return {"source": {"name": "OpenTargets", "url": "https://platform.opentargets.org", "batch_id": "DT001"}}


def test_build_targets_emits_source_name():
    targets_raw = pd.DataFrame([{
        "canonical_key": "uniprot:P31749",
        "ensembl_id": "ENSG00000142208",
        "gene_symbol": "AKT1",
        "approved_name": "RAC-alpha serine/threonine-protein kinase",
        "uniprot_accession": "P31749",
        "organism_tax_id": "9606",
    }])

    df = bc.build_targets(targets_raw, _cfg(), "2026-01-01")

    assert "source_name" in df.columns
    assert "source_id" not in df.columns
    assert df.iloc[0]["source_name"] == "OpenTargets"


def test_build_disease_targets_emits_source_name():
    cfg = _cfg()
    targets_raw = pd.DataFrame([{"canonical_key": "uniprot:P31749", "ensembl_id": "ENSG00000142208"}])
    targets_df = pd.DataFrame([{"canonical_key": "uniprot:P31749", "target_id": "t1"}])
    diseases_df = pd.DataFrame([{"disease_key": "d1", "disease_id": "d1"}])
    dt_raw = pd.DataFrame([{
        "canonical_key": "uniprot:P31749",
        "disease_id": "d1",
        "association_score": "0.8",
    }])

    df, _skipped = bc.build_disease_targets(dt_raw, targets_df, diseases_df, cfg, "2026-01-01", targets_raw)

    assert "source_name" in df.columns
    assert "source_id" not in df.columns
    assert df.iloc[0]["source_name"] == "OpenTargets"


def test_dedup_keeps_highest_score():
    """Duplicate (disease_id, target_id) pairs collapse to the highest-score row,
    regardless of source row order."""
    cfg = _cfg()
    targets_raw = pd.DataFrame([{"canonical_key": "uniprot:P31749", "ensembl_id": "ENSG00000142208"}])
    targets_df = pd.DataFrame([{"canonical_key": "uniprot:P31749", "target_id": "t1"}])
    diseases_df = pd.DataFrame([{"disease_key": "d1", "disease_id": "d1"}])
    # Lower score FIRST so an order-based keep="first" would wrongly keep 0.2.
    dt_raw = pd.DataFrame([
        {"canonical_key": "uniprot:P31749", "disease_id": "d1", "association_score": "0.2"},
        {"canonical_key": "uniprot:P31749", "disease_id": "d1", "association_score": "0.8"},
    ])

    df, _skipped = bc.build_disease_targets(dt_raw, targets_df, diseases_df, cfg, "2026-01-01", targets_raw)

    assert len(df) == 1
    assert float(df.iloc[0]["score"]) == 0.8
