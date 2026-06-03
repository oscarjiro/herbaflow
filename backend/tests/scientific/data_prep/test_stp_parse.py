import pytest
from tests.scientific.data_prep.stp_parse import (
    parse_stp_csv_text, filter_and_normalize, aggregate_targets,
)

pytestmark = pytest.mark.scientific

SAMPLE = (
    "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,Known actives (3D/2D)\n"
    "Aldose reductase,AKR1B1,P15121,CHEMBL1900,Enzyme,0.95,30/100\n"
    "Some kinase,AKT1,P31749,CHEMBL4282,Kinase,0.61,5/10\n"
    "Low conf,TP53,P04637,CHEMBL4096,TF,0.40,1/2\n"
)


def test_parse_then_filter_keeps_high_prob_only():
    rows = parse_stp_csv_text(SAMPLE)
    kept = filter_and_normalize(rows, min_prob=0.6)
    assert kept == ["AKR1B1", "AKT1"]  # TP53 dropped (0.40 < 0.6), order preserved


def test_aggregate_dedups_across_molecules():
    per_mol = [["AKR1B1", "AKT1"], ["AKT1", "EGFR"], []]
    agg = aggregate_targets(per_mol)
    assert agg == ["AKR1B1", "AKT1", "EGFR"]  # sorted unique
