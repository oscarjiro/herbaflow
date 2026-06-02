# etl/tests/test_s3_disease_targets.py
import importlib.util
from pathlib import Path

import pandas as pd

_PATH = Path(__file__).resolve().parents[1] / "disease_targets" / "03_build_canonical" / "run.py"
_spec = importlib.util.spec_from_file_location("dt_build_canonical", _PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CFG = {"source": {"name": "Open Targets", "url": "https://platform.opentargets.org", "batch_id": "b1"}}


def test_build_targets_source_url_is_ot_target_deep_link():
    raw = pd.DataFrame([{
        "canonical_key": "uniprot:P04637", "ensembl_id": "ENSG00000141510",
        "gene_symbol": "TP53", "approved_name": "Cellular tumor antigen p53",
        "uniprot_accession": "P04637", "organism_tax_id": "9606",
    }])
    out = _mod.build_targets(raw, CFG, "2026-01-01T00:00:00Z")
    assert out.iloc[0]["source_url"] == "https://platform.opentargets.org/target/ENSG00000141510"


def test_build_disease_targets_link_source_url():
    targets_raw = pd.DataFrame([{"canonical_key": "uniprot:P04637", "ensembl_id": "ENSG00000141510"}])
    targets_df = _mod.build_targets(targets_raw, CFG, "2026-01-01T00:00:00Z")
    diseases_df = pd.DataFrame([{"disease_key": "doid:1612", "disease_id": "d-uuid"}])
    dt_raw = pd.DataFrame([{
        "canonical_key": "uniprot:P04637", "disease_key": "doid:1612",
        "disease_id": "d-uuid", "association_score": "0.9", "efo_id": "EFO:0000305",
    }])
    out, _skipped = _mod.build_disease_targets(dt_raw, targets_df, diseases_df, CFG,
                                               "2026-01-01T00:00:00Z", targets_raw)
    url = out.iloc[0]["source_url"]
    assert url == "https://platform.opentargets.org/evidence/ENSG00000141510/EFO_0000305"
