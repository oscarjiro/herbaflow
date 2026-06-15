"""Pure unit tests for the export wiring: the PPI-figure decision point (stored STRING image
preferred over the local render, with a safe fallback) and the not-applicable-stage bundle skip.
No DB, no external calls."""

from __future__ import annotations

import base64
import io
import zipfile
from typing import Any

from app.pipeline import report
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
        docking="docking",
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
