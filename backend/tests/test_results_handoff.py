from app.pipeline import results_handoff as rh


def _csv_rows(text: str) -> list[list[str]]:
    import csv
    import io

    return [r for r in csv.reader(io.StringIO(text)) if r and not r[0].startswith("#")]


SR_FULL = {
    "3": {
        "compound_targets": [
            {"compound_id": "c1", "target_id": "t1", "prediction_method": "chembl_bioactivity", "gene_symbol": "PPARG"},
            {"compound_id": "c2", "target_id": "t1", "prediction_method": "pubchem_bioassay", "gene_symbol": "PPARG"},
            {"compound_id": "c1", "target_id": "t9", "prediction_method": "chembl_bioactivity", "gene_symbol": "OFF"},
        ]
    },
    "5": {"overlap": [{"target_id": "t1", "gene_symbol": "PPARG", "uniprot_accession": "P37231", "opentargets_score": 0.8}]},
    "7": {"hubs": [{"rank": 1, "target_id": "t1", "gene_symbol": "PPARG"}]},
    "8": {"terms": [{"source": "KEGG", "term_id": "KEGG:04151", "name": "PI3K-Akt", "p_value": 1.2e-4, "intersection": ["PPARG"]}]},
}
COMPOUNDS = {
    "c1": {"name": "CURCUMIN", "inchi_key": "VFLDPWHFBUODDF-FCXRPNKRSA-N", "smiles": "CC=O"},
    "c2": {"name": "ASPIRIN", "inchi_key": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N", "smiles": "O=Cc1ccccc1"},
}
TARGETS = {"t1": {"gene_symbol": "PPARG", "uniprot_accession": "P37231"}}


def test_ctp_nodes_has_binding_compounds_overlap_targets_and_pathways():
    text = rh.build_ctp_nodes(SR_FULL, COMPOUNDS, TARGETS)
    rows = _csv_rows(text)
    header, data = rows[0], rows[1:]
    assert header == ["id", "label", "type", "inchikey", "uniprot_accession", "is_hub", "source"]
    by_type = {}
    for r in data:
        by_type.setdefault(r[2], []).append(r)
    assert {r[0] for r in by_type["compound"]} == {"c1", "c2"}
    assert by_type["target"][0][0] == "PPARG"
    assert by_type["target"][0][4] == "P37231"
    assert by_type["target"][0][5] == "true"
    assert by_type["pathway"][0][0] == "KEGG:04151"
    assert by_type["pathway"][0][6] == "KEGG"
