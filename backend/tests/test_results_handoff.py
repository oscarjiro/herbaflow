import io as _io
import zipfile as _zipfile

from app.pipeline import results_handoff as rh


def _csv_rows(text: str) -> list[list[str]]:
    import csv
    import io

    return [r for r in csv.reader(io.StringIO(text)) if r and not r[0].startswith("#")]


SR_FULL = {
    "3": {
        "compound_targets": [
            {
                "compound_id": "c1",
                "target_id": "t1",
                "prediction_method": "chembl_bioactivity",
                "gene_symbol": "PPARG",
            },
            {
                "compound_id": "c2",
                "target_id": "t1",
                "prediction_method": "pubchem_bioassay",
                "gene_symbol": "PPARG",
            },
            {
                "compound_id": "c1",
                "target_id": "t9",
                "prediction_method": "chembl_bioactivity",
                "gene_symbol": "OFF",
            },
        ]
    },
    "5": {
        "overlap": [
            {
                "target_id": "t1",
                "gene_symbol": "PPARG",
                "uniprot_accession": "P37231",
                "opentargets_score": 0.8,
            }
        ]
    },
    "7": {"hubs": [{"rank": 1, "target_id": "t1", "gene_symbol": "PPARG"}]},
    "8": {
        "terms": [
            {
                "source": "KEGG",
                "term_id": "KEGG:04151",
                "name": "PI3K-Akt",
                "p_value": 1.2e-4,
                "intersection": ["PPARG"],
            }
        ]
    },
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
    assert header == [
        "id",
        "label",
        "type",
        "inchikey",
        "smiles",
        "uniprot_accession",
        "is_hub",
        "source",
    ]
    by_type = {}
    for r in data:
        by_type.setdefault(r[2], []).append(r)
    # compound node id is now the de-UUID'd InChIKey, not the raw compound_id
    assert {r[0] for r in by_type["compound"]} == {
        COMPOUNDS["c1"]["inchi_key"],
        COMPOUNDS["c2"]["inchi_key"],
    }
    assert {r[4] for r in by_type["compound"]} == {
        COMPOUNDS["c1"]["smiles"],
        COMPOUNDS["c2"]["smiles"],
    }
    assert by_type["target"][0][0] == "PPARG"
    assert by_type["target"][0][5] == "P37231"
    assert by_type["target"][0][6] == "true"
    assert by_type["pathway"][0][0] == "KEGG:04151"
    assert by_type["pathway"][0][7] == "KEGG"


def test_ctp_edges_ct_into_overlap_and_tp_from_term_intersection():
    text = rh.build_ctp_edges(SR_FULL, COMPOUNDS, TARGETS)
    rows = _csv_rows(text)
    header, data = rows[0], rows[1:]
    assert header == ["source", "target", "interaction", "prediction_method", "p_value"]
    ct = [r for r in data if r[2] == "compound-target"]
    tp = [r for r in data if r[2] == "target-pathway"]
    # C-T edge source endpoints reference the de-UUID'd compound node ids (InChIKey)
    assert sorted((r[0], r[1]) for r in ct) == sorted(
        [
            (COMPOUNDS["c1"]["inchi_key"], "PPARG"),
            (COMPOUNDS["c2"]["inchi_key"], "PPARG"),
        ]
    )
    assert all(r[1] != "OFF" for r in ct)
    assert ct[0][3] in {"chembl_bioactivity", "pubchem_bioassay"}
    assert (tp[0][0], tp[0][1], tp[0][2]) == ("PPARG", "KEGG:04151", "target-pathway")
    assert tp[0][4] != ""


def test_docking_table_one_row_per_hub_x_binding_compound_alphafold_is_accession():
    text = rh.build_docking_table(SR_FULL, COMPOUNDS, TARGETS)
    rows = _csv_rows(text)
    header, data = rows[0], rows[1:]
    assert header == [
        "hub_gene_symbol",
        "hub_uniprot_accession",
        "alphafold_id",
        "compound_name",
        "compound_inchikey",
        "compound_smiles",
        "prediction_method",
        "source_url",
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


def test_build_report_is_interpretive():
    # build_report is now a thin delegate to the report model + renderer (the single home for the
    # run's human-readable science). The output is the new interpretive markdown, not the old
    # "Result count: N" shape.
    run_meta = {
        "analysis_id": "a1",
        "name": "Curcuma x T2DM",
        "mode": "guided",
        "created_at": "2026-06-14T00:00:00Z",
        "completed_at": "2026-06-14T00:02:00Z",
    }
    params = {
        "enrichment": {
            "significance_threshold": 0.05,
            "correction": "fdr",
            "sources": ["GO:BP", "KEGG"],
            "no_iea": False,
            "min_term_size": 5,
        },
    }
    labels = {"plant": "Curcuma longa", "disease": "Type 2 Diabetes Mellitus"}
    md = rh.build_report(
        run_meta,
        params,
        SR_FULL,
        labels,
        input_modes={},
        frontend_url="https://herbaflow.app",
        figures=[],
    )
    assert "Result count:" not in md
    assert "## Stage 5 — Target overlap" in md
    assert "mechanistic core" in md


_SR = {
    "3": {
        "compound_targets": [
            {"compound_id": "c1", "target_id": "t1", "prediction_method": "chembl"},
            {"compound_id": "c2", "target_id": "t9", "prediction_method": "chembl"},  # not overlap
        ]
    },
    "5": {"overlap": [{"target_id": "t1", "gene_symbol": "PPARG", "uniprot_accession": "P37231"}]},
    "7": {"hubs": [{"target_id": "t1", "gene_symbol": "PPARG"}]},
    "8": {
        "terms": [
            {
                "term_id": "GO:0001",
                "name": "x",
                "source": "GO:BP",
                "p_value": 0.001,
                "intersection": ["PPARG"],
            }
        ]
    },
}
_COMP = {"c1": {"name": "Curcumin", "inchi_key": "VFLDPWHFBUODDF-FCXRPNKRSA-N", "smiles": "O=C"}}
_TGT = {"t1": {"gene_symbol": "PPARG", "uniprot_accession": "P37231"}}


def test_ctp_compound_node_id_is_inchikey_with_smiles():
    graph = rh.build_ctp_graph(_SR, _COMP, _TGT)
    comp = next(n for n in graph["nodes"] if n["type"] == "compound")
    assert comp["id"] == "VFLDPWHFBUODDF-FCXRPNKRSA-N"
    assert comp["smiles"] == "O=C"


def test_ctp_edge_endpoints_match_node_ids():
    graph = rh.build_ctp_graph(_SR, _COMP, _TGT)
    node_ids = {n["id"] for n in graph["nodes"]}
    for e in graph["edges"]:
        assert e["source"] in node_ids
        assert e["target"] in node_ids


def test_ctp_nodes_csv_has_smiles_header():
    assert rh.build_ctp_nodes(_SR, _COMP, _TGT).splitlines()[0] == (
        "id,label,type,inchikey,smiles,uniprot_accession,is_hub,source"
    )


_SR6 = {
    "6": {
        "nodes": [
            {"gene_symbol": "PPARG", "target_id": "t1", "uniprot_accession": "P37231"},
            {"gene_symbol": "TP53", "target_id": "t2", "uniprot_accession": "P04637"},
        ],
        "edges": [{"source": "PPARG", "target": "TP53", "confidence": 0.92}],
    },
    "7": {"hubs": [{"target_id": "t1", "gene_symbol": "PPARG"}]},
}


def test_ppi_nodes_have_hub_flag_and_join():
    graph = rh.build_ppi_graph(_SR6)
    node_ids = {n["id"] for n in graph["nodes"]}
    assert node_ids == {"PPARG", "TP53"}
    assert next(n for n in graph["nodes"] if n["id"] == "PPARG")["is_hub"] == "true"
    for e in graph["edges"]:
        assert e["source"] in node_ids and e["target"] in node_ids


def test_ppi_edges_csv_header():
    assert rh.build_ppi_edges(_SR6).splitlines()[0] == "source,target,confidence"


def test_ppi_nodes_csv_header():
    assert rh.build_ppi_nodes(_SR6).splitlines()[0] == "id,gene_symbol,uniprot_accession,is_hub"


def test_stage5_csv_columns_and_values():
    out = rh.build_stage_csv(5, _SR, _COMP, _TGT)
    assert out.splitlines()[0] == "gene_symbol,uniprot_accession,opentargets_score"
    assert "PPARG,P37231," in out  # opentargets_score may be blank in this fixture


def test_stage7_csv_columns():
    sr = {
        "7": {
            "hubs": [
                {
                    "rank": 1,
                    "gene_symbol": "PPARG",
                    "uniprot_accession": "P37231",
                    "degree": 0.5,
                    "betweenness": 0.2,
                    "closeness": 0.4,
                    "eigenvector": 0.3,
                    "composite": 0.41,
                }
            ]
        }
    }
    head = rh.build_stage_csv(7, sr, {}, {}).splitlines()[0]
    assert head == (
        "rank,gene_symbol,uniprot_accession,degree,betweenness,closeness,eigenvector,composite"
    )


def test_empty_stage_emits_note():
    out = rh.build_stage_csv(8, {"8": {"terms": []}}, {}, {})
    assert out.splitlines()[0].startswith("term_id")
    assert "# no enriched terms" in out


def test_stage1_csv_columns_and_values():
    out = rh.build_stage_csv(1, _SR1, _COMP1, {})
    assert out.splitlines()[0] == "compound,inchikey,smiles"
    assert "Curcumin,VFLDPWHFBUODDF-FCXRPNKRSA-N,O=C" in out


def test_stage1_csv_empty_note():
    out = rh.build_stage_csv(1, {"1": {"compounds": []}}, {}, {})
    assert out.splitlines()[0] == "compound,inchikey,smiles"
    assert "# no compounds" in out


def test_stage2_csv_columns_and_buckets():
    out = rh.build_stage_csv(2, _SR2, {}, {})
    assert out.splitlines()[0] == (
        "compound_id,canonical_name,passed,descriptor_source,molecular_weight,logp,"
        "hbond_donors,hbond_acceptors,tpsa,rotatable_bonds,qed_score,np_likeness_score,"
        "num_ro5_violations,is_pains_positive,source_url,reason"
    )
    assert "c1,Curcumin,true," in out
    assert "c2,Aspirin,false," in out


def test_stage3_csv_columns():
    head = rh.build_stage_csv(3, _SR3, {}, {}).splitlines()[0]
    assert head == "gene_symbol,uniprot_accession,prediction_method,source_url"


def test_stage4_csv_columns():
    head = rh.build_stage_csv(4, _SR4, {}, {}).splitlines()[0]
    assert head == "gene_symbol,uniprot_accession,opentargets_score,source_url"


def test_stage6_csv_is_ppi_edge_list():
    assert rh.build_stage_csv(6, _SR6, {}, {}).splitlines()[0] == "source,target,confidence"


_SR1 = {"1": {"compounds": [{"compound_id": "c1", "canonical_name": "Curcumin"}]}}
_COMP1 = {"c1": {"name": "Curcumin", "inchi_key": "VFLDPWHFBUODDF-FCXRPNKRSA-N", "smiles": "O=C"}}
_SR2 = {
    "2": {
        "passed": [
            {
                "compound_id": "c1",
                "canonical_name": "Curcumin",
                "descriptor_source": "etl",
                "molecular_weight": 368.38,
                "logp": 3.2,
                "hbond_donors": 2,
                "hbond_acceptors": 6,
                "tpsa": 93.06,
                "rotatable_bonds": 8,
                "qed_score": 0.5,
                "np_likeness_score": 1.1,
                "num_ro5_violations": 0,
                "is_pains_positive": True,
                "source_url": "https://pubchem.ncbi.nlm.nih.gov/compound/969516",
                "badges": ["pains"],
            }
        ],
        "filtered": [
            {
                "compound_id": "c2",
                "canonical_name": "Aspirin",
                "descriptor_source": "etl",
                "molecular_weight": 180.16,
                "logp": 1.2,
                "hbond_donors": 1,
                "hbond_acceptors": 4,
                "tpsa": 63.6,
                "rotatable_bonds": 3,
                "qed_score": 0.55,
                "np_likeness_score": -0.5,
                "num_ro5_violations": 0,
                "is_pains_positive": False,
                "source_url": None,
                "reason": "1 Lipinski violation(s)",
            }
        ],
    }
}
_SR3 = {
    "3": {
        "targets": [
            {
                "target_id": "t1",
                "gene_symbol": "PPARG",
                "uniprot_accession": "P37231",
                "prediction_method": "chembl_bioactivity",
                "source_url": "https://www.uniprot.org/uniprotkb/P37231",
            }
        ]
    }
}
_SR4 = {
    "4": {
        "targets": [
            {
                "target_id": "t1",
                "gene_symbol": "PPARG",
                "uniprot_accession": "P37231",
                "opentargets_score": 0.8,
                "association_type": "genetic_association",
                "source_url": "https://www.uniprot.org/uniprotkb/P37231",
            }
        ]
    }
}


def test_report_no_uuid_in_body_and_has_branding():
    meta = {
        "analysis_id": "abcd-uuid",
        "name": None,
        "mode": "auto",
        "created_at": "2026-06-14T00:00:00+00:00",
        "completed_at": "2026-06-14T00:01:00+00:00",
    }
    params = {"disease_targets": {"min_score": 0.3}}
    md = rh.build_report(
        meta,
        params,
        _SR,
        {"plant": "Curcuma longa", "disease": "T2DM"},
        input_modes={},
        frontend_url="https://herbaflow.app",
        figures=[],
    )
    assert "abcd-uuid" not in md  # no analysis UUID in the body
    assert md.startswith("# Herbaflow Analysis — Curcuma longa and T2DM")  # branded default title
    assert "https://herbaflow.app" in md  # configurable Herbaflow link
    assert "ChEMBL" in md  # per-stage data sources (computed)


def test_report_honest_sources_for_user_provided_stage():
    md = rh.build_report(
        {
            "analysis_id": "x",
            "name": "Run",
            "mode": "auto",
            "created_at": "t",
            "completed_at": "t",
        },
        {},
        _SR,
        {"plant": "P", "disease": "D"},
        input_modes={"plant": "manual_targets"},
        frontend_url="u",
        figures=[],
    )
    # manual_targets => S3 user_provided => only UniProt named, not ChEMBL
    assert "UniProt (manual target resolution)" in md


def test_network_readme_has_cytoscape_steps():
    md = rh.build_network_readme()
    assert "Import Network from File" in md
    assert "Import Table from File" in md
    assert "ctp-nodes.csv" in md and "ctp-edges.csv" in md and "docking.csv" in md


def test_stages_readme_lists_files():
    md = rh.build_stages_readme()
    assert "stage5_overlap.csv" in md and "stage8_enrichment.csv" in md


def test_root_readme_lists_bundles():
    md = rh.build_root_readme()
    assert "report.md" in md and "network-and-docking" in md.lower() and "stages/" in md


def _names(data: bytes) -> set[str]:
    return set(_zipfile.ZipFile(_io.BytesIO(data)).namelist())


def test_network_bundle_contents():
    b = rh.build_network_bundle(
        ctp_nodes="a", ctp_edges="b", docking="c", network_png=None, readme="r"
    )
    # network_png=None -> png omitted; CSVs + README always present
    assert _names(b) == {"ctp-nodes.csv", "ctp-edges.csv", "docking.csv", "README.md"}


def test_network_bundle_includes_png_when_present():
    b = rh.build_network_bundle(
        ctp_nodes="a", ctp_edges="b", docking="c", network_png=b"\x89PNG", readme="r"
    )
    assert "ctp-network.png" in _names(b)


def test_all_results_superset_layout():
    b = rh.build_all_results_bundle(
        report="rep",
        network_files={"ctp-nodes.csv": "n"},
        stage_files={"stage5_overlap.csv": "o"},
    )
    names = _names(b)
    assert "README.txt" in names and "report.md" in names
    assert "network-and-docking/ctp-nodes.csv" in names
    assert "stages/stage5_overlap.csv" in names


def test_docking_table_has_source_url():
    csv = rh.build_docking_table(SR_FULL, COMPOUNDS, TARGETS)
    header = csv.splitlines()[0]
    assert header.endswith("source_url")
    assert "alphafold.ebi.ac.uk" in csv


def test_report_threads_included_figures_into_stage_sections():
    # The figures keyword flows through the delegate to the report model: an included figure is
    # referenced inline under its stage; an omitted one is not surfaced.
    md = rh.build_report(
        {"name": "R", "mode": "auto", "created_at": "t", "completed_at": "t"},
        {},
        _SR,
        {"plant": "P", "disease": "D"},
        input_modes={},
        frontend_url="u",
        figures=[
            ("stage5_venn.png", True, "empty overlap"),
            ("stage7_hub_bar.png", False, "no hub genes"),
        ],
    )
    assert "`stage5_venn.png`" in md
    assert "stage7_hub_bar.png" not in md
