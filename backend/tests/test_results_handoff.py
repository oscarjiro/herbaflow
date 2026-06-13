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


def test_ctp_edges_ct_into_overlap_and_tp_from_term_intersection():
    text = rh.build_ctp_edges(SR_FULL)
    rows = _csv_rows(text)
    header, data = rows[0], rows[1:]
    assert header == ["source", "target", "interaction", "prediction_method", "p_value"]
    ct = [r for r in data if r[2] == "compound-target"]
    tp = [r for r in data if r[2] == "target-pathway"]
    assert sorted((r[0], r[1]) for r in ct) == [("c1", "PPARG"), ("c2", "PPARG")]
    assert all(r[1] != "OFF" for r in ct)
    assert ct[0][3] in {"chembl_bioactivity", "pubchem_bioassay"}
    assert (tp[0][0], tp[0][1], tp[0][2]) == ("PPARG", "KEGG:04151", "target-pathway")
    assert tp[0][4] != ""


def test_docking_table_one_row_per_hub_x_binding_compound_alphafold_is_accession():
    text = rh.build_docking_table(SR_FULL, COMPOUNDS, TARGETS)
    rows = _csv_rows(text)
    header, data = rows[0], rows[1:]
    assert header == [
        "hub_gene_symbol", "hub_uniprot_accession", "alphafold_id",
        "compound_name", "compound_inchikey", "compound_smiles", "prediction_method",
    ]
    assert len(data) == 2
    assert all(r[0] == "PPARG" for r in data)
    assert all(r[1] == "P37231" and r[2] == "P37231" for r in data)
    assert {r[3] for r in data} == {"CURCUMIN", "ASPIRIN"}


def test_docking_table_empty_hub_set_yields_header_plus_note():
    sr = {**SR_FULL, "7": {"hubs": []}}
    text = rh.build_docking_table(sr, COMPOUNDS, TARGETS)
    assert text.splitlines()[0].startswith("hub_gene_symbol")
    assert any(line.startswith("#") for line in text.splitlines())


def test_report_has_inputs_counts_params_and_no_version_checksums():
    run_meta = {
        "analysis_id": "a1", "name": "Curcuma x T2DM", "mode": "guided",
        "created_at": "2026-06-14T00:00:00Z", "completed_at": "2026-06-14T00:02:00Z",
    }
    params = {
        "enrichment": {"significance_threshold": 0.05, "correction": "fdr",
                       "sources": ["GO:BP", "KEGG"], "no_iea": False, "min_term_size": 5},
    }
    labels = {"plant": "Curcuma longa", "disease": "Type 2 Diabetes Mellitus"}
    md = rh.build_report(run_meta, params, SR_FULL, labels)
    assert "Curcuma longa" in md and "Type 2 Diabetes Mellitus" in md
    assert "significance_threshold" in md and "no_iea" in md
    assert "overlap" in md.lower()
    assert "no source-version" in md.lower() or "no version" in md.lower()


def test_report_partial_run_notes_na_stages_and_na_labels():
    sr = {"3": SR_FULL["3"], "5": SR_FULL["5"]}
    md = rh.build_report({"analysis_id": "a2", "name": "m", "mode": "auto",
                          "created_at": "x", "completed_at": "y"},
                         {}, sr, {"plant": None, "disease": None})
    assert "N/A" in md


def test_bundle_contains_the_four_named_files():
    import io
    import zipfile

    data = rh.build_bundle(
        ctp_nodes="id,label\n", ctp_edges="source,target\n",
        docking="hub_gene_symbol\n", report="# r\n",
    )
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert set(zf.namelist()) == {"ctp-nodes.csv", "ctp-edges.csv", "docking.csv", "report.md"}
        assert zf.read("report.md").decode() == "# r\n"
