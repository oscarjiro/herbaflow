# etl/tests/test_provenance.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/ on path for `shared`
from shared import provenance as p


def test_gbif_species_url():
    assert p.gbif_species_url("12345") == "https://www.gbif.org/species/12345"
    assert p.gbif_species_url("") is None
    assert p.gbif_species_url(None) is None


def test_pubchem_compound_url():
    assert p.pubchem_compound_url("2244") == "https://pubchem.ncbi.nlm.nih.gov/compound/2244"
    assert p.pubchem_compound_url("") is None


def test_chembl_compound_url():
    assert p.chembl_compound_url("CHEMBL25") == \
        "https://www.ebi.ac.uk/chembl/compound_report_card/CHEMBL25"
    assert p.chembl_compound_url("") is None


def test_uniprot_url():
    assert p.uniprot_url("P04637") == "https://www.uniprot.org/uniprotkb/P04637/entry"
    assert p.uniprot_url("") is None


def test_opentargets_target_url():
    assert p.opentargets_target_url("ENSG00000141510") == \
        "https://platform.opentargets.org/target/ENSG00000141510"
    assert p.opentargets_target_url("") is None


def test_opentargets_target_assoc_url():
    assert p.opentargets_target_assoc_url("ENSG00000141510") == \
        "https://platform.opentargets.org/target/ENSG00000141510/associations"
    assert p.opentargets_target_assoc_url("") is None


def test_opentargets_evidence_url_precise_when_efo_present():
    assert p.opentargets_evidence_url("ENSG00000141510", "EFO:0000270") == \
        "https://platform.opentargets.org/evidence/ENSG00000141510/EFO_0000270"


def test_opentargets_evidence_url_falls_back_to_assoc_without_efo():
    assert p.opentargets_evidence_url("ENSG00000141510", "") == \
        "https://platform.opentargets.org/target/ENSG00000141510/associations"
    assert p.opentargets_evidence_url("", "EFO:0000270") is None


def test_knapsack_metabolite_url():
    assert p.knapsack_metabolite_url("C00000001") == \
        "http://www.knapsackfamily.com/knapsack_core/information.php?word=C00000001"
    assert p.knapsack_metabolite_url("") is None


def test_disease_ontology_url():
    assert p.disease_ontology_url("DOID", "DOID:1612") == "https://disease-ontology.org/?id=DOID:1612"
    assert p.disease_ontology_url("Disease Ontology", "DOID:1612") == \
        "https://disease-ontology.org/?id=DOID:1612"
    # Stored OBO underscore form normalizes to the colon CURIE the DO site expects.
    assert p.disease_ontology_url("Disease Ontology", "DOID_1612") == \
        "https://disease-ontology.org/?id=DOID:1612"
    assert p.disease_ontology_url("DOID", "DOID_0080208") == \
        "https://disease-ontology.org/?id=DOID:0080208"
    assert p.disease_ontology_url("MeSH", "D001943") == \
        "https://meshb.nlm.nih.gov/record/ui?ui=D001943"
    assert p.disease_ontology_url("Unknown", "X") is None
    assert p.disease_ontology_url("MeSH", "") is None


def test_build_source_url_dispatch():
    assert p.build_source_url("GBIF", gbif_usage_key="12345") == "https://www.gbif.org/species/12345"
    assert p.build_source_url("PubChem", pubchem_cid="2244") == \
        "https://pubchem.ncbi.nlm.nih.gov/compound/2244"
    assert p.build_source_url("Open Targets", ensembl_id="ENSG1") == \
        "https://platform.opentargets.org/target/ENSG1"
    assert p.build_source_url("UniProt", uniprot_accession="P04637") == \
        "https://www.uniprot.org/uniprotkb/P04637/entry"
    assert p.build_source_url("KNApSAcK", c_id="C1") == \
        "http://www.knapsackfamily.com/knapsack_core/information.php?word=C1"
    assert p.build_source_url("nonsense") is None


def test_resolve_source_url_falls_back_to_base():
    assert p.resolve_source_url("PubChem", "https://base", pubchem_cid="2244") == \
        "https://pubchem.ncbi.nlm.nih.gov/compound/2244"
    assert p.resolve_source_url("PubChem", "https://base") == "https://base"
    assert p.resolve_source_url("nonsense", "https://base") == "https://base"
