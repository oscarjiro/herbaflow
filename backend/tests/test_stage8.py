import pytest

from app.integrations.gprofiler import EnrichedTerm, GprofilerError
from app.pipeline.stages import stage8


def _term(native="KEGG:04151", size=354, isize=2, inter=("AKT1", "TNF")):
    return EnrichedTerm(
        source="KEGG",
        native=native,
        name="PI3K-Akt",
        p_value=1e-5,
        term_size=size,
        query_size=3,
        intersection_size=isize,
        intersection=list(inter),
        significant=True,
    )


def _s3(genes):
    return {
        "targets": [
            {"target_id": f"t{i}", "gene_symbol": g, "uniprot_accession": f"P{i}"}
            for i, g in enumerate(genes)
        ],
        "count": len(genes),
        "state": "computed",
    }


def _s5(genes):
    return {
        "overlap": [
            {
                "target_id": f"t{i}",
                "gene_symbol": g,
                "uniprot_accession": f"P{i}",
                "disease_association_score": 0.5,
            }
            for i, g in enumerate(genes)
        ],
        "count": len(genes),
        "state": "computed",
    }


class _FakeGprofiler:
    def __init__(self, terms=None, *, fail=False):
        self._terms = terms or []
        self._fail = fail
        self.seen = {}

    async def profile(self, *, query, background, sources, correction, user_threshold):
        if self._fail:
            raise GprofilerError("down")
        self.seen = {
            "query": query,
            "background": background,
            "sources": sources,
            "correction": correction,
            "user_threshold": user_threshold,
        }
        return list(self._terms)


@pytest.mark.asyncio
async def test_compute_assembles_query_and_background_and_filters_min_term_size():
    fake = _FakeGprofiler([_term(native="GO:1", size=2), _term(native="KEGG:04151", size=354)])
    out = await stage8.compute(
        _s5(["AKT1", "TNF"]),
        _s3(["AKT1", "TNF", "EGFR", "TP53"]),
        client=fake,
        fdr_threshold=0.05,
        sources=["GO:BP", "KEGG"],
        correction="fdr",
        min_term_size=5,
    )
    assert sorted(fake.seen["query"]) == ["AKT1", "TNF"]
    assert sorted(fake.seen["background"]) == ["AKT1", "EGFR", "TNF", "TP53"]
    assert fake.seen["correction"] == "fdr" and fake.seen["user_threshold"] == 0.05
    # the GO:1 term (size 2 < min_term_size 5) is dropped
    assert [t["term_id"] for t in out["terms"]] == ["KEGG:04151"]
    assert out["terms"][0]["intersection"] == ["AKT1", "TNF"]
    assert out["background_source"] == "compound_target_universe"
    assert out["background_gene_count"] == 4
    assert out["degraded"] is False
    assert out["count"] == 1


@pytest.mark.asyncio
async def test_compute_empty_query_is_honest_null():
    fake = _FakeGprofiler([])
    out = await stage8.compute(
        _s5([]),
        _s3(["AKT1"]),
        client=fake,
        fdr_threshold=0.05,
        sources=["GO:BP"],
        correction="fdr",
        min_term_size=5,
    )
    assert out["terms"] == [] and out["count"] == 0
    assert "empty_input" in out["flags"]


@pytest.mark.asyncio
async def test_compute_degrades_on_outage_without_raising():
    fake = _FakeGprofiler(fail=True)
    out = await stage8.compute(
        _s5(["AKT1", "TNF"]),
        _s3(["AKT1", "TNF", "EGFR"]),
        client=fake,
        fdr_threshold=0.05,
        sources=["GO:BP"],
        correction="fdr",
        min_term_size=5,
    )
    assert out["degraded"] is True
    assert "source_degraded" in out["flags"]
    assert out["terms"] == [] and out["count"] == 0
    assert out["state"] == "computed"  # still a valid terminal result
