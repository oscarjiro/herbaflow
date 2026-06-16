# Golden-dataset validation: Curcumin and Colorectal Cancer

This is a literature-concordance validation of the Herbaflow eight-stage network-pharmacology pipeline against a fixed panel of peer-reviewed studies. The full export bundle for the validated run is attached under `artifacts/` as proof.

## 1. Overview

This report validates the Herbaflow network-pharmacology pipeline on a single, well-studied pair: the compound Curcumin (InChIKey VFLDPWHFBUODDF-FCXRPNKRSA-N) against Colorectal Cancer (DOID:9256). Curcumin is the defining phytochemical of turmeric (Curcuma longa) and a widely studied Indonesian-jamu constituent. The run uses the manual single-compound entry mode: the compound is supplied directly and the disease is selected from the catalog, so the pipeline starts at compound-target identification rather than at plant-to-compound mapping.

The reference for comparison is a fixed panel of four peer-reviewed curcumin network-pharmacology studies of colorectal (or colon) cancer. The panel was fixed before any score was computed. Each study used a different target-prediction method, so the panel deliberately disagrees with itself; concordance is therefore measured against the panel as a whole and reported, never asserted against any single paper.

| Study | Journal | DOI | Reported contribution |
| --- | --- | --- | --- |
| Han et al. 2021 | Evid Based Complement Alternat Med | [10.1155/2021/9132608](https://doi.org/10.1155/2021/9132608) | core hubs AKT1, EGFR, STAT3; PI3K-Akt signaling |
| He et al. 2023 | Front Pharmacol | [10.3389/fphar.2023.1102581](https://doi.org/10.3389/fphar.2023.1102581) | cell-cycle targets CDK2, AURKA/B, CHEK1, TYMS, DNMT1, TOP2A |
| Yuan et al. 2026 | Front Pharmacol | [10.3389/fphar.2025.1703562](https://doi.org/10.3389/fphar.2025.1703562) | ferroptosis and Wnt/beta-catenin; hubs SIRT1, SERPINE1, MMP3, WNT5A |
| Wu et al. 2025 | Transl Cancer Res | [10.21037/tcr-2025-359](https://doi.org/10.21037/tcr-2025-359) | MDM2, COX-2 (PTGS2); Western-blot validation |

### Fixtures used

The run is deterministic and offline. It replays recorded external responses so the result is reproducible and does not depend on the live state of any external service:

- `gd1_seed.json`
- `gd1_string_network.json`
- `gd1_gprofiler.json`
- `gd1_reference_genes.json`
- `gd1_snapshot.json`

## 2. Evaluation methodology

The evaluation framework is pre-registered: it was fixed before any number was judged, to avoid tuning the criteria so the result passes. It composes two recognized methodologies. The regression layer uses golden-master (characterization) testing, which captures the pipeline's current output on frozen inputs and asserts it stays stable. The scientific layer uses criterion-validity assessment, which measures the agreement of a new instrument with an accepted reference using standard agreement statistics.

The framework has three levels:

- **Level A: structural and regression integrity.** A hard pass or fail. All applicable stages are present and well-formed; the overlap stage is a pure intersection; the hub stage ranks by Maximal Clique Centrality in descending order; and re-running on the frozen inputs reproduces the identical overlap set and hub ordering. This is the only layer wired to continuous integration.
- **Level B: methodological fidelity.** A recorded judgment, per stage, of how Herbaflow's method relates to the reference's, drawn from {equivalent, stricter, different-but-valid, not applicable}. This is documented, not scored.
- **Level C: scientific concordance.** The criterion-validity scores (C1, C2, C3). These are computed and reported. They are never bound to continuous integration, because a future paper may revise the reference.

The pre-registered verdict rubric: a test is successful when Level A passes, and the disease's own pathway is recovered (C1 yes), and the hub set is significantly over-represented for reference genes (Fisher exact p < 0.05) or precision@10 is at least 0.6.

## 3. Implementation

The regression test seeds the captured canonical data into a throwaway Postgres instance, replays the recorded external responses, drives a single-compound run through all applicable stages, and asserts a frozen snapshot of the scientific output (overlap count, hub ranking, recovered pathway). The reference gene set is loaded from a curated fixture assembled from the panel papers. The two source files below are reproduced verbatim.

### Regression test (Level A)

`backend/tests/scientific/test_golden_gd1.py`

```python
"""GD-1 golden regression: curcumin x colorectal cancer, auto mode, all 8 stages, OFFLINE.

Level-A deterministic snapshot test (opt-in ``@pytest.mark.scientific``, deselected by default).
Seeds the captured canonical data, replays the recorded STRING + g:Profiler responses, drives a
manual-single-compound x selected-disease run end-to-end, and asserts a frozen snapshot of the
scientific output (overlap count, MCC hub ranking, enrichment terms). Stage 3 stays fully offline
via D9 edge-reuse; the Stage-3 client guards in ``patch_gd1`` prove no live call is made.
"""

import pytest

from tests.scientific.conftest import load_json, poll_run
from tests.scientific.gd1_support import patch_gd1, seed_gd1

pytestmark = pytest.mark.scientific


@pytest.mark.asyncio
async def test_gd1_curcumin_crc_snapshot(golden_client, monkeypatch):
    c, engine = golden_client
    seed = await seed_gd1(engine)
    patch_gd1(monkeypatch)
    snap = load_json("gd1_snapshot.json")

    resp = await c.post(
        "/analyses",
        json={
            "plant_input_mode": "manual_compounds",
            "manual_compound_ids": [seed["curcumin_compound_id"]],
            "disease_input_mode": "selection",
            "disease_id": seed["disease_id"],
            "mode": "auto",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    state = await poll_run(c, run_id)
    assert state["status"] == "complete", state.get("error_message")

    sr = state["stage_results"]

    # Stage 5: raw overlap (no statistics): the field-standard set intersection.
    assert sr["5"]["count"] == snap["overlap_count"]
    for k in snap["stage5_forbidden_keys"]:
        assert k not in sr["5"]

    # Stage 7: MCC hub ranking (Chin 2014), sole ranker.
    assert sr["7"]["ranking_metric"] == snap["ranking_metric"]
    hubs = [h["gene_symbol"] for h in sorted(sr["7"]["hubs"], key=lambda h: -h["mcc"])]
    assert hubs[:5] == snap["mcc_top5"]

    # Stage 8: functional enrichment includes the disease pathway.
    enr = {t["name"] for t in sr["8"]["terms"]}
    for term in snap["enrichment_includes"]:
        assert term in enr
```

### Reference gene-set loader

`backend/scripts/golden/reference.py`

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_FIX = Path(__file__).resolve().parents[2] / "tests" / "scientific" / "fixtures"


@dataclass(frozen=True)
class ReferenceSet:
    gene_set: set[str]
    universe: int
    _papers: dict[str, list[str]]

    def papers_for(self, gene: str) -> list[str]:
        return self._papers.get(gene, [])


def load_gd1() -> ReferenceSet:
    data = json.loads((_FIX / "gd1_reference_genes.json").read_text(encoding="utf-8"))
    genes = data["genes"]
    return ReferenceSet(
        set(genes),
        int(data["universe"]),
        {g: meta.get("papers", []) for g, meta in genes.items()},
    )


@dataclass(frozen=True)
class Gd2HubMetric:
    """The reference study's reported figures for one top-10 hub gene."""

    rank: int
    gene_symbol: str
    degree: float
    betweenness: float
    closeness: float
    eigenvector: float
    score: float


@dataclass(frozen=True)
class Gd2Reference:
    """The reference (Hito) pancreatic-cancer hub ranking and shared-target set.

    ``hito_top10`` is the reference's top-10 gene symbols ordered best-first (ascending rank).
    ``overlap_233`` is the reference study's reported 233-gene shared-target set. ``metrics`` maps
    each top-10 gene symbol to its reported rank, four centralities, and composite score, for the
    hub comparison table. Pure: this reads JSON only and computes nothing.
    """

    hito_top10: tuple[str, ...]
    overlap_233: frozenset[str]
    metrics: dict[str, Gd2HubMetric]

    def rank_of(self, gene: str) -> int | None:
        m = self.metrics.get(gene)
        return m.rank if m is not None else None

    def score_of(self, gene: str) -> float | None:
        m = self.metrics.get(gene)
        return m.score if m is not None else None


def load_gd2() -> Gd2Reference:
    data = json.loads((_FIX / "gd2_hub_ref.json").read_text(encoding="utf-8"))
    rows = sorted(data["hub_genes"], key=lambda r: r["rank"])
    metrics = {
        r["gene_symbol"]: Gd2HubMetric(
            rank=int(r["rank"]),
            gene_symbol=r["gene_symbol"],
            degree=float(r["degree"]),
            betweenness=float(r["betweenness"]),
            closeness=float(r["closeness"]),
            eigenvector=float(r["eigenvector"]),
            score=float(r["score"]),
        )
        for r in rows
    }
    return Gd2Reference(
        hito_top10=tuple(r["gene_symbol"] for r in rows),
        overlap_233=frozenset(data["overlap_233"]),
        metrics=metrics,
    )
```

## 4. Stage-by-stage comparison (Stage 1 to 8)

Each cell gives the count and the tool or source that paper reported for that stage, or "not reported" when the paper does not state it. Every number is transcribed from the cited paper. The reference panel uses single curcumin and predicted compound targets, while Herbaflow uses measured bioactivity, so the downstream sets differ by construction. He et al. study colon cancer; the others study colorectal cancer.

| Stage | Herbaflow | Han 2021 | He 2023 | Yuan 2026 | Wu 2025 |
| --- | --- | --- | --- | --- | --- |
| 1 Compound | not run (manual single compound) | curcumin (PubChem) | curcumin (PubChem, CAS 458-37-7) | curcumin (PubChem) | curcumin (PubChem/RHAWN) |
| 2 ADME | RDKit Lipinski/Veber; curcumin passes | SwissADME, Lipinski rule of five; passes | not reported | not reported | not reported |
| 3 Compound to target | 104 measured (ChEMBL + PubChem BioAssay) | 104 (SwissTargetPrediction, p>0, Homo sapiens) | 448 (PharmMapper + SwissTargetPrediction + TargetNet + SuperPred) | 264 (ChEMBL + STRING + literature) | 60 (STITCH, confidence 0.7, Homo sapiens) |
| 4 Disease to target | 746 (Open Targets, at or above the score floor) | 1911 (GeneCards/OMIM/TTD/DrugBank) | 704 (GEO GSE74602 DEGs intersected with OMIM/DisGeNET/GeneCards) | 47,261 (GeneCards/DrugBank/DisGeNET/CTD, score above median) | not reported (GeneCards; CRC plus apoptosis) |
| 5 Overlap | 15 (set intersection) | 30 (Jvenn) | 73 (Venny) | 46 (Venny; plus RNA-seq DEGs 3328) | 25 (curcumin, CRC, apoptosis triple) |
| 6 PPI | 15 nodes, 55 edges (STRING) | 26 nodes, 90 edges (STRING 0.4) | 70 nodes, 230 edges (STRING) | 42 nodes, 232 edges (STRING v11.5, 0.5, Homo sapiens) | 25 input genes; nodes/edges not reported (STRING) |
| 7 Hubs | 10 (MCC, Chin 2014) | 3 core by degree (NetworkAnalyzer + CytoNCA): AKT1, EGFR, STAT3 | 10 (cytoHubba top-15 intersection of Degree/MNC/MCC/Closeness): CDK2, TOP2A, CCNA2, AURKA, AURKB, CHEK1, TYMS, TK1, DNMT1, HSP90AA1 | 11 (cytoHubba degree plus median; MCODE 8.364): ESR1, JUN, SIRT1, SERPINE1, ICAM1, HMOX1, CHUK, EP300, MMP3, PTGS1, WNT5A | none (validated MDM2, COX-2; no hub-ranking stage) |
| 8 Enrichment | 101 (g:Profiler GO+KEGG); CRC present | 61 KEGG, 140 GO (DAVID, P<0.05); CRC present | 34 KEGG, 256 GO (DAVID); CRC not in top-20 | 33 pathways, 106 GO (DAVID, P<0.05 and FDR<0.05); CRC not in top-20 | about 30 KEGG, 24 GO (R clusterProfiler); CRC present |

Level-B methodological judgment (Herbaflow versus the panel as a whole):

- Stage 1: not applicable (Herbaflow starts from the supplied compound)
- Stage 2: different-but-valid (RDKit drug-likeness versus SwissADME)
- Stage 3: different-but-valid (measured bioactivity versus predicted targets)
- Stage 4: different-but-valid (Open Targets scored versus text-mined unions)
- Stage 5: equivalent (set intersection)
- Stage 6: equivalent (STRING PPI)
- Stage 7: equivalent (MCC / cytoHubba family)
- Stage 8: equivalent (GO/KEGG enrichment)

## 5. Output comparison

### Overlap (candidate therapeutic targets)

Herbaflow intersects 104 measured compound targets with 746 disease targets (Open Targets association score at or above the default floor) to give an overlap of 15 genes: NFE2L2, SMAD3, EP300, RARA, RXRA, PTGS2, PTGS1, TP53, EGFR, TLR9, NFKB2, SMAD2, NSD2, TOP1, JUN. The panel papers report overlaps of comparable size from their own predicted target sets; the exact membership differs because the input universes differ (measured versus predicted).

### Hub genes (Maximal Clique Centrality)

The protein-protein interaction network over the overlap has 15 nodes and 55 edges. The top-10 hubs by Maximal Clique Centrality (the cytoHubba method, Chin et al. 2014), with independent corroboration per hub:

| Hub | MCC rank | MCC score | Reported by panel paper(s) | Open Targets CRC score | In CTD curcumin-CRC |
| --- | --- | --- | --- | --- | --- |
| SMAD3 | 1 | 2952 | not in panel | 0.681 | not assessed |
| TP53 | 2 | 2936 | not in panel | 0.832 | not assessed |
| JUN | 3 | 2934 | not in panel | 0.534 | not assessed |
| EP300 | 4 | 2930 | not in panel | 0.740 | not assessed |
| EGFR | 5 | 2912 | Han 2021 | 0.769 | not assessed |
| PTGS2 | 6 | 1516 | Wu 2025 | 0.449 | not assessed |
| NFE2L2 | 7 | 1488 | not in panel | 0.483 | not assessed |
| RARA | 8 | 1464 | not in panel | 0.435 | not assessed |
| SMAD2 | 9 | 1440 | not in panel | 0.666 | not assessed |
| RXRA | 10 | 50 | not in panel | 0.509 | not assessed |

The CTD (Comparative Toxicogenomics Database) cross-check is a deferred open item: each hub is marked "not assessed" rather than guessed. The Open Targets colorectal cancer association score is the value Herbaflow already stores for each disease target.

### Compound-target-pathway network versus the reference drug-target-pathway network

Herbaflow's exported compound-target-pathway network has 117 nodes and 888 edges, connecting the compound to its overlap targets and those targets to the enriched pathways. The panel papers present an analogous drug-target-pathway (or compound-target-pathway) figure; the structure is the same (a tripartite compound, target, pathway graph), the size differs with each paper's target set. The full node and edge lists are attached as Cytoscape-importable CSVs.

### Enrichment pathways

Functional enrichment returns 101 significant terms. The KEGG pathways include: Pathways in cancer, Hepatocellular carcinoma, Human T-cell leukemia virus 1 infection, Colorectal cancer, Wnt signaling pathway, Breast cancer, Gastric cancer, Pancreatic cancer. The presence of the "Colorectal cancer" KEGG pathway is the disease-pathway recovery check (C1).

## 6. Final evaluation (Level C scores)

### C1: disease-pathway recovery (binary)

Is the disease's own KEGG pathway present in the enrichment result? "Colorectal cancer" present: **yes**.

### C2: pathway-panel concordance

Overlap and Jaccard index between Herbaflow's significant pathways and the panel's reported pathway set (PI3K-Akt signaling, p53 signaling, Wnt / Wnt-beta-catenin signaling, Arachidonic acid / COX-2, Cell cycle). Matched panel pathways: Wnt / Wnt-beta-catenin signaling (1 of 5). Jaccard index: **0.200**.

### C3: hub corroboration

Over Herbaflow's top-10 Maximal Clique Centrality hubs against the 19-gene curated reference set:

- precision@10 = **0.200** (2 of 10 hubs are reference genes: EGFR, PTGS2).
- one-sided Fisher exact test of over-representation: p = **3.83e-05**, odds ratio = **293.72**. The universe is the human protein-coding genome (20,000 genes), stated explicitly; the reference set is 19 genes; the draw is the 10 hubs.

## 7. Verdict

**SUCCESSFUL**

Level A (the regression snapshot test) passes. The disease pathway "Colorectal cancer" is recovered (C1 yes). The hub set is significantly over-represented for reference genes (Fisher exact p = 3.83e-05, odds ratio 293.7), driven by recognized colorectal-cancer hubs such as EGFR, PTGS2.

Honest note on hub-level divergence. Herbaflow derives compound targets from measured bioactivity, while the panel papers derive them from target-prediction software. The two input universes differ by construction, so an exact hub-for-hub match with any single panel paper is not expected and is not the success criterion. The success criterion is that the hubs Herbaflow recovers are significantly over-represented for genes the field independently validated, and that the disease's own pathway is recovered. A low precision@10 against the panel union is expected and reflects this measured-versus-predicted input difference, not a defect in the pipeline.

### Notes

- The full export bundle for this run is committed under `artifacts/` as proof: per-stage CSVs, chart PNGs, the Cytoscape network tables, and the run's own report.
