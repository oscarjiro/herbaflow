from scripts.golden import report


def test_gd1_stage_matrix_renders_per_paper_columns():
    rows = [
        report.Gd1StageMatrixRow(
            "3 Compound to target",
            "104 measured",
            "104 (STP)",
            "448",
            "264",
            "60 (STITCH)",
        )
    ]
    md = report._section_stage_comparison(
        report.ReportModel(
            compound_name="curcumin",
            compound_inchikey="X",
            disease_name="Colorectal Cancer",
            disease_key="DOID:9256",
            entry_mode="manual single-compound",
            panel=[],
            fixtures=[],
            compound_target_count=104,
            disease_target_count=746,
            overlap_count=15,
            overlap_genes=[],
            ppi_node_count=15,
            ppi_edge_count=55,
            enrichment_term_count=101,
            top10_hubs=[],
            code_excerpts=[],
            stage_rows=[],
            hub_rows=[],
            ctp_node_count=0,
            ctp_edge_count=0,
            enrichment_kegg_terms=[],
            artifact_files=[],
            reference_gene_count=19,
            reference_universe=20000,
            reference_genes=[],
            c1_present=True,
            c1_term="Colorectal cancer",
            c2_matched=[],
            c2_panel_set=[],
            c2_jaccard=0.2,
            c2_overlap_count=1,
            c3_precision_at_10=0.2,
            c3_hits_in_reference=2,
            c3_hub_genes_in_reference=[],
            c3_fisher_p=3.8e-5,
            c3_fisher_odds=293.7,
            level_a_pass=True,
            verdict_successful=True,
            verdict_reason="ok",
            stage_matrix=rows,
            level_b_rows=[("3", "different-but-valid (measured versus predicted)")],
        )
    )
    assert "Han 2021" in md and "He 2023" in md and "Yuan 2026" in md and "Wu 2025" in md
    assert "104 (STP)" in md
    assert "different-but-valid" in md
