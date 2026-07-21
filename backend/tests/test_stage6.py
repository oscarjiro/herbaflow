import base64

import pytest

from app.integrations.string_db import StringEdge
from app.pipeline.genes import distinct_gene_symbol_rows
from app.pipeline.stages import stage6


def _overlap(n, base_score=0.5):
    return {
        "overlap": [
            {
                "target_id": f"t{i}",
                "gene_symbol": f"G{i}",
                "uniprot_accession": f"P{i}",
                "opentargets_score": base_score + i * 0.001,
            }
            for i in range(n)
        ],
        "count": n,
        "state": "computed",
    }


def test_build_result_parses_edges_and_nodes():
    rows = [
        {"gene_symbol": "G0", "target_id": "t0", "uniprot_accession": "P0"},
        {"gene_symbol": "G1", "target_id": "t1", "uniprot_accession": "P1"},
        {"gene_symbol": "G2", "target_id": "t2", "uniprot_accession": "P2"},
    ]
    edges = [StringEdge("G0", "G1", 0.6)]
    out = stage6.build_result(
        rows,
        edges,
        min_confidence=0.4,
        network_type="functional",
    )
    assert out["state"] == "computed"
    assert out["edge_count"] == 1 and out["node_count"] == 3
    # G2 has no edge but is an isolated node, still listed
    assert {n["gene_symbol"] for n in out["nodes"]} == {"G0", "G1", "G2"}
    assert out["count"] == 3


def test_nodes_carry_target_id_and_accession():
    stage5 = {
        "overlap": [
            {
                "target_id": "t1",
                "gene_symbol": "AKT1",
                "uniprot_accession": "P31749",
                "opentargets_score": 0.7,
            },
            {
                "target_id": "t2",
                "gene_symbol": "TNF",
                "uniprot_accession": "P01375",
                "opentargets_score": 0.6,
            },
        ]
    }
    rows = distinct_gene_symbol_rows(stage5["overlap"])
    result = stage6.build_result(
        rows,
        [StringEdge("AKT1", "TNF", 0.9)],
        min_confidence=0.4,
        network_type="functional",
    )
    by_gene = {n["gene_symbol"]: n for n in result["nodes"]}
    assert by_gene["AKT1"]["target_id"] == "t1"
    assert by_gene["AKT1"]["uniprot_accession"] == "P31749"
    assert by_gene["TNF"]["target_id"] == "t2"
    assert by_gene["TNF"]["uniprot_accession"] == "P01375"
    assert result["node_count"] == 2 and result["edge_count"] == 1


class _FakeRun:
    def __init__(self, overlap):
        self.stage_results = {"5": overlap}
        self.parameters = {
            "ppi": {
                "min_confidence": 0.4,
                "network_type": "functional",
            }
        }


class _StubStringClient:
    """Records the args of both calls; returns canned edges + a canned image (or None)."""

    def __init__(self, *, edges, image):
        self._edges = edges
        self._image = image
        self.network_args = None
        self.image_args = None

    async def network(self, gene_symbols, *, min_confidence, network_type):
        self.network_args = (list(gene_symbols), min_confidence, network_type)
        return self._edges

    async def fetch_network_image(self, gene_symbols, *, min_confidence, network_type):
        self.image_args = (list(gene_symbols), min_confidence, network_type)
        return self._image


@pytest.mark.asyncio
async def test_run_persists_server_image_base64_when_present():
    png = b"\x89PNG\r\n\x1a\nfake-image-bytes"
    client = _StubStringClient(edges=[StringEdge("G0", "G1", 0.6)], image=png)
    run = _FakeRun(_overlap(3))

    result = await stage6.run(None, run, client=client)

    assert result["network_image"] == base64.b64encode(png).decode("ascii")
    # core result unchanged by the image step
    assert result["state"] == "computed"
    assert result["node_count"] == 3
    assert result["edge_count"] == 1
    assert {n["gene_symbol"] for n in result["nodes"]} == {"G0", "G1", "G2"}


@pytest.mark.asyncio
async def test_run_omits_image_key_when_fetch_returns_none():
    client = _StubStringClient(edges=[StringEdge("G0", "G1", 0.6)], image=None)
    run = _FakeRun(_overlap(3))

    result = await stage6.run(None, run, client=client)

    assert "network_image" not in result
    # the stage still succeeds with the normal result
    assert result["state"] == "computed"
    assert result["node_count"] == 3
    assert result["edge_count"] == 1


@pytest.mark.asyncio
async def test_run_sends_every_overlap_symbol_to_string():
    """There is no protein-count cap: every overlap gene symbol reaches STRING.

    STRING imposes no maximum identifier count when the species is set, and this stage always
    sends 9606, so the network is always built over the full overlap and is never blocked.
    """
    client = _StubStringClient(edges=[StringEdge("G0", "G1", 0.6)], image=b"png")
    run = _FakeRun(_overlap(3))

    result = await stage6.run(None, run, client=client)

    # No blocked marker — the stage computed the full network.
    assert "blocked" not in result
    assert result["state"] == "computed"
    assert result["node_count"] == 3
    assert "capped" not in result
    # STRING received ALL three overlap gene symbols.
    assert client.network_args is not None
    assert set(client.network_args[0]) == {"G0", "G1", "G2"}
    assert client.image_args is not None
    assert set(client.image_args[0]) == {"G0", "G1", "G2"}


@pytest.mark.asyncio
async def test_run_image_fetch_uses_same_args_as_network():
    png = b"img"
    client = _StubStringClient(edges=[], image=png)
    run = _FakeRun(_overlap(3))

    await stage6.run(None, run, client=client)

    assert client.network_args is not None
    assert client.image_args is not None
    # same symbols / min_confidence / network_type for both calls
    assert client.image_args == client.network_args
    assert client.network_args == (["G0", "G1", "G2"], 0.4, "functional")
