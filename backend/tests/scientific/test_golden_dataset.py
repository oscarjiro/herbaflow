"""Golden-dataset scientific validation (opt-in: `pytest -m scientific`).

Read tests/scientific/VALIDATION.md first — it records the verified Li-2025 comparison and
WHY these tests assert pipeline behaviour, not literature hub-recall, for the Open-Targets
(seeded) disease path.

Framing (see VALIDATION.md for the evidence)
--------------------------------------------
PRIMARY reference: Li M, Zhang C et al. 2025, Front Nutr, doi:10.3389/fnut.2025.1710380.
  Verified network-pharmacology arm: 304 curcumin targets (STP+TargetNet+SuperPred+STITCH),
  7,768 T2DM targets (OMIM/TTD/GeneCards/PharmGKB/MalaCards ~39% of the genome), 256 overlap,
  hubs AKT1/TNF/TP53/IL6/EGFR (only AKT1+TP53 confirmed by docking), KEGG AGE-RAGE + PI3K-Akt.
  Li publishes no importable gene list; the paper adds in-vivo mouse + docking + qRT-PCR.
SUPPORTING only: Mahmoudi 2022 (doi:10.3390/nu14153244); Nguyen & Kim 2022 (doi:10.1016/j.abb.2022.109326).
METHODOLOGY: SwissTargetPrediction (Daina et al. 2019); golden-dataset practice (Mangul 2019;
  Cock 2015). STP is used here only to mirror Li's compound side; the platform's production
  compound->target path is ChEMBL + PubChem BioAssay.

P1/P2 use the SEEDED Open-Targets T2DM path. The Li hubs (AKT1/EGFR absent; IL6/TNF/TP53 < 0.3
default) cannot enter the overlap via Open Targets, so these tests assert PIPELINE BEHAVIOUR
(all 8 stages run, overlap + significance computed, artifacts produced) and only REPORT the Li
hub/pathway comparison. A small or non-significant overlap is the honest result of a stricter,
more specific methodology than Li's 39%-of-genome disease set — never weaken anything to match
Li, and never assert his hubs through the Open-Targets path. Literature hub/overlap assertion
lives in P3 (thesis manual disease targets; user-gated).
"""
import pytest

from tests.scientific.conftest import (
    T2DM_DISEASE_ID,
    create_and_run,
    export_all_stages,
    load_gene_fixture,
)
from tests.scientific.renderers import render_centrality, render_enrichment, render_ppi

# Li-2025 anchors — REPORTED for human review, NOT asserted on the Open-Targets path.
CUR_HUBS = {"AKT1", "TNF", "TP53", "IL6", "EGFR"}
CUR_PATHWAYS = {"04933", "04151"}  # AGE-RAGE, PI3K-Akt (match on numeric suffix)

pytestmark = pytest.mark.scientific

ALL_STAGES = {f"stage_{i}" for i in range(1, 9)}


def _hub_symbols(detail: dict) -> set[str]:
    ranked = detail["stage_results"].get("stage_7", {}).get("ranked", [])
    return {r["gene_symbol"].upper() for r in ranked}


def _kegg_suffixes(detail: dict) -> set[str]:
    kegg = detail["stage_results"].get("stage_8", {}).get("kegg", [])
    return {t["term_id"].split(":")[-1].lstrip("hsa") for t in kegg}


def _write_artifacts(detail, artifacts_dir):
    sr = detail["stage_results"]
    return [
        render_ppi(sr.get("stage_6", {}), artifacts_dir),
        render_centrality(sr.get("stage_7", {}), artifacts_dir),
        render_enrichment(sr.get("stage_8", {}), artifacts_dir),
    ]


def _report_vs_li(label: str, detail: dict) -> None:
    """Print the qualitative Li comparison (Tier-3, human review). Never asserts."""
    sr = detail["stage_results"]
    s5 = sr.get("stage_5", {})
    hubs = _hub_symbols(detail)
    print(
        f"\n[{label}] Li-2025 qualitative comparison (NOT asserted on the OT path):\n"
        f"  compound targets : {len(sr.get('stage_3', {}).get('target_gene_symbols', []))} (Li: 304)\n"
        f"  disease targets  : {len(sr.get('stage_4', {}).get('disease_gene_symbols', []))} (Li: 7,768)\n"
        f"  overlap_count    : {s5.get('overlap_count')} (Li: 256)\n"
        f"  p_value/jaccard  : {s5.get('p_value')} / {s5.get('jaccard')} (Li: not tested)\n"
        f"  overlap genes    : {sorted(s5.get('overlap', []))}\n"
        f"  Li hubs present  : {sorted(CUR_HUBS & hubs)} of {sorted(CUR_HUBS)}\n"
        f"  Li pathways hit  : {sorted(CUR_PATHWAYS & _kegg_suffixes(detail))}\n"
    )


def _assert_pipeline_ran(detail: dict) -> None:
    """Regression invariants: every stage ran and Stage-5 overlap statistics are well-formed.
    Deterministic given the frozen STP fixture + DB-cached T2DM set; independent of live STRING/
    g:Profiler magnitudes. Does NOT assert significance or literature hub-recall (see VALIDATION.md)."""
    sr = detail["stage_results"]
    assert ALL_STAGES <= set(sr), f"missing stages: {ALL_STAGES - set(sr)}"

    s5 = sr["stage_5"]
    assert isinstance(s5["overlap_count"], int) and s5["overlap_count"] >= 1, s5
    assert len(s5.get("overlap", [])) == s5["overlap_count"]
    p = s5["p_value"]
    assert isinstance(p, (int, float)) and 0.0 <= p <= 1.0, p
    j = s5["jaccard"]
    assert isinstance(j, (int, float)) and 0.0 <= j <= 1.0, j
    assert "significant" in s5  # honesty flag is emitted (not gated on)


@pytest.mark.asyncio
async def test_p2_curcumin_t2dm(api_client, artifacts_dir):
    """P2 (curcumin x T2DM, Open-Targets seeded): pipeline regression + qualitative Li report.
    See VALIDATION.md — hub/pathway recall is NOT asserted here (AKT1/EGFR are absent from the
    OT T2DM set; IL6/TNF/TP53 sit below the 0.3 cutoff)."""
    targets = load_gene_fixture("curcumin_stp_targets.csv")
    assert targets, "curcumin STP fixture is empty — run Stage 2a first"

    detail = await create_and_run(
        api_client, name="golden-P2-curcumin-T2DM",
        targets=targets, disease_id=T2DM_DISEASE_ID,
    )

    _assert_pipeline_ran(detail)
    _report_vs_li("P2 curcumin", detail)

    await export_all_stages(api_client, detail["_analysis_id"], artifacts_dir)
    for path in _write_artifacts(detail, artifacts_dir):
        import os
        assert os.path.exists(path), path
