import os

import pytest

from tests.scientific.renderers import render_centrality, render_enrichment, render_ppi

pytestmark = pytest.mark.scientific


def test_render_ppi_writes_png(tmp_path):
    stage6 = {"raw_edges": [{"source": "AKT1", "target": "TP53", "combined_score": 0.9},
                            {"source": "AKT1", "target": "EGFR", "combined_score": 0.7}]}
    out = render_ppi(stage6, str(tmp_path))
    assert os.path.exists(out) and os.path.getsize(out) > 0


def test_render_centrality_writes_png(tmp_path):
    stage7 = {"ranked": [{"gene_symbol": "AKT1", "composite_score": 0.9},
                         {"gene_symbol": "TP53", "composite_score": 0.8}]}
    out = render_centrality(stage7, str(tmp_path))
    assert os.path.exists(out) and os.path.getsize(out) > 0


def test_render_enrichment_writes_png(tmp_path):
    stage8 = {"kegg": [{"term_id": "KEGG:04933", "term_name": "AGE-RAGE", "fdr": 0.001},
                       {"term_id": "KEGG:04151", "term_name": "PI3K-Akt", "fdr": 0.01}]}
    out = render_enrichment(stage8, str(tmp_path))
    assert os.path.exists(out) and os.path.getsize(out) > 0


def test_render_ppi_handles_empty(tmp_path):
    out = render_ppi({"raw_edges": []}, str(tmp_path))
    assert os.path.exists(out)  # writes an empty-graph placeholder, no crash
