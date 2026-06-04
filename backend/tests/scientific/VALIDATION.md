# Golden-dataset scientific validation — methodology & findings

This document records *why* the golden-dataset suite (`pytest -m scientific`) asserts what it
asserts, and the verified literature comparison behind it. Read this before changing any
threshold in `test_golden_dataset.py`.

## What the suite validates

The 8-stage pipeline, driven end-to-end through the **real API** (a live uvicorn server),
for a curcumin / *Curcuma longa* × Type-2-Diabetes (T2DM) dataset. It is **opt-in and
non-CI** (hits live STRING + g:Profiler; SwissTargetPrediction fixtures are scraped once,
offline). It is not part of the fast unit gate.

## Primary reference — Li et al. 2025 (verified against the published article)

**Li M, Zhang C, et al. (2025).** *Curcumin attenuates liver injury by modulating the
AGE–RAGE axis and metabolic homeostasis in high-fat diet/streptozotocin-induced type 2
diabetic mice.* Front. Nutr. 12, 07 Nov 2025. doi:10.3389/fnut.2025.1710380 (IF ≈ 5.1).

This is primarily an **in-vivo mouse study** (HFD/STZ T2D model) with **molecular docking
and qRT-PCR wet-lab validation** of the curcumin/AGE-RAGE/T2DM mechanism — substantially
more credible than a predict-and-publish network-pharmacology paper. Its network-pharmacology
arm (the part we compare to) reports, **verified from the article**:

| Item | Li 2025 |
| --- | --- |
| Curcumin targets | **304** (SwissTargetPrediction + TargetNet + SuperPred + STITCH — 4-tool union) |
| T2DM targets | **7,768** (OMIM + TTD + GeneCards + PharmGKB + MalaCards — 5-DB union; ≈39% of the genome) |
| Overlap (Venny 2.1.0) | **256** |
| PPI (STRING, conf >0.4) | 254 nodes / 4,291 edges; avg degree 33.79 |
| Hub genes (by degree) | **AKT1, TNF, TP53, IL6, EGFR** |
| KEGG (168 paths, FDR<0.01) | top = **AGE–RAGE in diabetic complications**, PI3K-Akt, HIF-1, EGFR-TKI resistance |
| Docking caveat | only **AKT1, TP53** (and RAGE) bind curcumin favourably; **TNF, IL6, EGFR showed no significant binding** → 3 of the 5 "hubs" are network-topology artifacts, not confirmed curcumin targets (Li's own data) |

Li publishes **only these counts + the 5 hub names + figures** — there is **no downloadable
gene list** (supplementary material is a network figure + PCR primers). So Li's exact target
sets cannot be imported for a true reproduction.

Supporting (context only, NOT asserted against): Mahmoudi et al. 2022 (Nutrients,
doi:10.3390/nu14153244); Nguyen & Kim 2022 (Arch Biochem Biophys, doi:10.1016/j.abb.2022.109326).

## Why this platform does NOT reproduce Li's hub list (verified, not a defect)

Two deliberate, defensible methodology differences:

| Dimension | Li 2025 | This platform |
| --- | --- | --- |
| Compound→target | 4-tool union → **304** | **STP-only → 62** (higher precision, lower recall) |
| Disease→target | 5-DB union → **7,768** (~39% of genome) | **Open Targets** (score ≥0.3) → **911** (~4.5%) |
| Overlap | raw Venn → **256** | intersection + hypergeometric p + Jaccard → **4** (ATP2A3, DYRK2, NOS2, PTGS1), **p = 0.31 (n.s.)** |
| Hubs surfaced | AKT1/TNF/TP53/IL6/EGFR | none (4-gene overlap → no PPI/enrichment) |

**Verified root cause (Open Targets T2DM set):** AKT1 and EGFR are **absent entirely**;
IL6 (0.118), TNF (0.120), TP53 (0.107) are present but **all below the 0.3 default cutoff**.
So the Li hubs can never enter the compound∩disease overlap via the Open-Targets path — at
*any* threshold AKT1/EGFR are missing. This is structural to the disease source, not a bug.

This is defensible, not a weakness: Li's 7,768-gene disease set is ~39% of the genome, so a
256-overlap is near-trivial (expected ≈118 by chance). Open Targets is evidence-graded,
versioned, reproducible, and more specific — it deliberately excludes mechanism-only links.
The platform additionally reports overlap **significance** (hypergeometric p, Jaccard),
which the network-pharmacology literature usually omits.

## Consequence for the assertions

- **P2 (curcumin × T2DM, seeded OT path)** and **P1 (whole-plant × T2DM, seeded OT path)** are
  **pipeline-regression + qualitative** tests: assert the 8 stages complete, overlap is
  computed, a p-value/Jaccard and artifacts are produced; the Li hub/pathway comparison is
  **reported (printed) for human review, never asserted.** A small/non-significant overlap is
  an expected, honest result of the stricter methodology — **do not weaken anything to "match"
  Li, and do not assert his hubs through the Open-Targets path.**
- **P3 (thesis secondary, manual disease targets)** is the path that *can* carry hub/overlap
  assertions, because it injects a disease-gene-database target set (same methodology family as
  Li) rather than the Open-Targets associations. (User-gated on thesis fixtures.)

## Tooling notes

- **SwissTargetPrediction** (Daina et al. 2019, NAR): 2D/3D ligand-similarity reverse screening;
  keep Probability* ≥ 0.6, *Homo sapiens*. Free, web. Changed 2026-05-15 (ChemAxon removed) —
  the scraper is built against the current DOM. Note: STP is used **only for this golden test**;
  the platform's production compound→target path is ChEMBL + PubChem BioAssay.
- TargetNet (QSAR/ML), SuperPred (similarity+ML), STITCH (chemical–protein interaction DB) — all
  free; Li unions them for recall. This platform uses a single source for reproducibility.
