"""Pure unit tests for the export wiring: the PPI-figure decision point (stored STRING image
preferred over the local render, with a safe fallback), the not-applicable-stage bundle skip,
and the C-T-P emittability gate (compounds + overlap + pathways required).
No DB, no external calls."""

from __future__ import annotations

import base64
import io
import zipfile
from typing import Any

from app.pipeline import report
from app.pipeline.results_handoff import ctp_is_emittable
from app.services.export import ExportArtifacts, _ppi_figure

# A tiny PPI graph the matplotlib renderer can actually draw (one edge -> non-None bytes).
_PPI_GRAPH: dict[str, Any] = {
    "nodes": [
        {"id": "A", "gene_symbol": "A"},
        {"id": "B", "gene_symbol": "B"},
    ],
    "edges": [{"source": "A", "target": "B", "confidence": 0.9}],
}


def _png_b64() -> str:
    """A minimal but valid PNG (1x1) encoded base64, standing in for STRING's stored image."""
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return base64.b64encode(png).decode("ascii")


def test_ppi_figure_prefers_stored_string_image() -> None:
    """When sr["6"].network_image is present, return exactly its decoded bytes and DO NOT
    fall back to matplotlib. Pass an empty graph so the fallback would yield None: getting
    bytes back proves the stored path was taken."""
    encoded = _png_b64()
    sr = {"6": {"network_image": encoded}}
    out = _ppi_figure(sr, {}, hub_scores={}, min_confidence=0.4)
    assert out == base64.b64decode(encoded)


def test_ppi_figure_falls_back_to_render_when_no_stored_image() -> None:
    """No stored image -> matplotlib render. Bytes for a drawable graph, None for an empty one."""
    sr: dict[str, Any] = {"6": {}}
    out = _ppi_figure(sr, _PPI_GRAPH, hub_scores={}, min_confidence=0.4)
    assert isinstance(out, bytes) and len(out) > 0

    empty = _ppi_figure(sr, {"nodes": [], "edges": []}, hub_scores={}, min_confidence=0.4)
    assert empty is None


def test_ppi_figure_stage6_key_absent_falls_back() -> None:
    """sr with no "6" entry at all -> fall back to the local render (no crash)."""
    out = _ppi_figure({}, _PPI_GRAPH, hub_scores={}, min_confidence=0.4)
    assert isinstance(out, bytes) and len(out) > 0


def test_ppi_figure_malformed_base64_falls_back() -> None:
    """A malformed stored value must not raise; export falls back to the local render."""
    sr = {"6": {"network_image": "not!valid!base64!!"}}
    out = _ppi_figure(sr, _PPI_GRAPH, hub_scores={}, min_confidence=0.4)
    assert isinstance(out, bytes) and len(out) > 0


def _artifacts(input_modes: dict[str, Any]) -> ExportArtifacts:
    return ExportArtifacts(
        report="# report",
        stage_csvs={n: f"c{n}" for n in range(1, 9)},
        ctp_nodes="ctp_nodes",
        ctp_edges="ctp_edges",
        ppi_nodes="ppi_nodes",
        ppi_edges="ppi_edges",
        input_modes=input_modes,
    )


def _names(blob: bytes) -> list[str]:
    return zipfile.ZipFile(io.BytesIO(blob)).namelist()


def test_stages_bundle_drops_na_stage_csvs() -> None:
    """A manual-targets / selection run drops stage1 and stage2 CSVs; a selection run keeps them."""
    s1 = f"stage1_{report.STAGE_CSV_SLUG[1]}.csv"
    s2 = f"stage2_{report.STAGE_CSV_SLUG[2]}.csv"

    na = _names(_artifacts({"plant": "manual_targets", "disease": "selection"}).stages_bundle())
    assert s1 not in na
    assert s2 not in na

    full = _names(_artifacts({}).stages_bundle())
    assert s1 in full
    assert s2 in full


def test_all_results_bundle_drops_na_stage_csvs() -> None:
    """The all-results superset honors the same NA skip for its stages/ subdirectory."""
    s1 = f"stages/stage1_{report.STAGE_CSV_SLUG[1]}.csv"
    s2 = f"stages/stage2_{report.STAGE_CSV_SLUG[2]}.csv"

    na = _names(
        _artifacts({"plant": "manual_targets", "disease": "selection"}).all_results_bundle()
    )
    assert s1 not in na
    assert s2 not in na

    full = _names(_artifacts({}).all_results_bundle())
    assert s1 in full
    assert s2 in full


# ---------------------------------------------------------------------------
# C-T-P emittability gate
# ---------------------------------------------------------------------------

_SR_WITH_OVERLAP_AND_TERMS: dict[str, Any] = {
    "5": {"count": 3, "overlap": []},
    "8": {"count": 2, "terms": []},
}
_SR_ZERO_TERMS: dict[str, Any] = {
    "5": {"count": 3, "overlap": []},
    "8": {"count": 0, "terms": []},
}
_SR_ZERO_OVERLAP: dict[str, Any] = {
    "5": {"count": 0, "overlap": []},
    "8": {"count": 2, "terms": []},
}


def test_ctp_is_emittable_true_with_compounds_overlap_and_terms() -> None:
    assert ctp_is_emittable(_SR_WITH_OVERLAP_AND_TERMS, has_compounds=True) is True


def test_ctp_is_emittable_false_no_compounds() -> None:
    assert ctp_is_emittable(_SR_WITH_OVERLAP_AND_TERMS, has_compounds=False) is False


def test_ctp_is_emittable_false_zero_terms() -> None:
    assert ctp_is_emittable(_SR_ZERO_TERMS, has_compounds=True) is False


def test_ctp_is_emittable_false_zero_overlap() -> None:
    assert ctp_is_emittable(_SR_ZERO_OVERLAP, has_compounds=True) is False


def test_ctp_is_emittable_false_missing_stages() -> None:
    assert ctp_is_emittable({}, has_compounds=True) is False


def _ctp_artifacts(
    stage_results: dict[str, Any],
    has_compounds: bool = True,
) -> ExportArtifacts:
    return ExportArtifacts(
        report="# report",
        stage_csvs={n: f"c{n}" for n in range(1, 9)},
        ctp_nodes="ctp_nodes_content",
        ctp_edges="ctp_edges_content",
        ppi_nodes="ppi_nodes",
        ppi_edges="ppi_edges",
        has_compounds=has_compounds,
        stage_results=stage_results,
    )


def test_network_files_empty_when_zero_terms() -> None:
    """_network_files returns {} when Stage-8 terms=0, even with compounds and overlap."""
    a = _ctp_artifacts(_SR_ZERO_TERMS)
    assert a._network_files() == {}


def test_network_files_present_when_ctp_emittable() -> None:
    """_network_files returns the CTP CSVs when all three gates pass."""
    a = _ctp_artifacts(_SR_WITH_OVERLAP_AND_TERMS)
    files = a._network_files()
    assert "ctp-nodes.csv" in files
    assert "ctp-edges.csv" in files


def test_network_bundle_none_when_zero_terms() -> None:
    """network_bundle() returns None when Stage-8 terms=0."""
    a = _ctp_artifacts(_SR_ZERO_TERMS)
    assert a.network_bundle() is None


def test_network_bundle_bytes_when_ctp_emittable() -> None:
    """network_bundle() returns bytes when all three gates pass."""
    a = _ctp_artifacts(_SR_WITH_OVERLAP_AND_TERMS)
    bundle = a.network_bundle()
    assert isinstance(bundle, bytes) and len(bundle) > 0
    names = zipfile.ZipFile(io.BytesIO(bundle)).namelist()
    assert "ctp-nodes.csv" in names
    assert "ctp-edges.csv" in names


def test_all_results_bundle_omits_network_when_zero_terms() -> None:
    """The all-results bundle omits the network/ subdirectory when C-T-P is not emittable."""
    a = _ctp_artifacts(_SR_ZERO_TERMS)
    names = _names(a.all_results_bundle())
    assert not any(n.startswith("network/") for n in names)


def test_all_results_bundle_includes_network_when_ctp_emittable() -> None:
    """The all-results bundle includes network/ files when C-T-P is emittable."""
    a = _ctp_artifacts(_SR_WITH_OVERLAP_AND_TERMS)
    names = _names(a.all_results_bundle())
    assert any(n.startswith("network/") for n in names)
