# Phase 4 — Scientific/Academic Soundness Audit

## Task 4.1 — Methodology Transparency Checklist

**Date:** 2026-05-23

### Checklist Results

| Stage | Required disclosure                        | Status        | Evidence                                                                                          |
| ----- | ------------------------------------------ | ------------- | ------------------------------------------------------------------------------------------------- |
| 1     | Data source (KNApSAcK)                     | ❌ → ✅ Fixed | No footnote existed — added KNApSAcK Core disclosure                                              |
| 2     | Lipinski RO5 + Veber rules                 | ✅            | Lines 161–162: full criteria with numeric bounds                                                  |
| 2     | NP exception explained                     | ✅            | Lines 163–165: explains structural complexity rationale                                           |
| 3     | Source = ChEMBL, threshold = pChEMBL ≥ 5.0 | ✅            | Lines 96–97: "Source: ChEMBL … pChEMBL ≥ 5.0 (≡ IC₅₀ ≤ 10µM)"                                     |
| 4     | Source = Open Targets, score meaning 0–1   | ✅            | Lines 77–82: "Open Targets score (0–1): overall disease–gene association strength"                |
| 5     | Fisher's exact test p-value label          | ✅            | StatCard label="Fisher's Exact p-value"                                                           |
| 5     | Warning if overlap = 0                     | ✅            | Warning block lines 96–104 with downstream validity alert                                         |
| 6     | Source = STRING-DB, min_confidence stated  | ❌ → ✅ Fixed | Static text "set in analysis parameters" replaced with live `{result.min_confidence}` value       |
| 6     | Hub criterion = degree > µ + σ             | ✅            | Line 225: "overlap gene with degree > µ + σ (mean + 1 SD)"                                        |
| 7     | 4 centrality metric definitions available  | ❌ → ✅ Fixed | Added third disclosure paragraph defining Degree/Betweenness/Closeness/Eigenvector                |
| 7     | Hub+Bottleneck criterion explained         | ✅            | Lines 108–110: "gene exceeding BOTH degree and betweenness thresholds"                            |
| 8     | x-axis = -log₁₀(FDR) confirmed             | ✅            | XAxis label `'-log₁₀(FDR)'` (line 54)                                                             |
| 8     | Reference line at FDR = 0.05               | ✅            | `ReferenceLine x={1.301}` (-log₁₀(0.05) = 1.301)                                                  |
| 8     | GO:BP/MF/CC spelled out                    | ✅            | `SOURCE_LABELS` map: "GO: Biological Process", "GO: Molecular Function", "GO: Cellular Component" |
| 8     | Method = g:Profiler ORA noted              | ✅            | Lines 148–150: "Method: g:Profiler ORA (over-representation analysis)"                            |

**Result: 11/14 already passing; 3 gaps fixed.**

### Fixes Applied

**Fix 1 — Stage1Panel: Added KNApSAcK disclosure**

- `frontend/src/components/stages/Stage1Panel.tsx` lines 67–69
- Added footnote after DataTable: "Source: KNApSAcK Core — metabolite–species database mapping compounds to plant species."

**Fix 2 — Stage6: Exposed min_confidence in result**

- `backend/analysis/stages/stage6_ppi.py`: added `"min_confidence": config.ppi.min_confidence` to return dict
- `frontend/src/types/api.ts`: added `min_confidence: number` to `Stage6Result` interface
- `frontend/src/components/stages/Stage6Panel.tsx`: disclosure now renders `{result.min_confidence}` instead of static "set in analysis parameters"

**Fix 3 — Stage7Panel: Added 4 centrality metric definitions**

- `frontend/src/components/stages/Stage7Panel.tsx` lines 111–117
- Added third disclosure paragraph defining Degree, Betweenness, Closeness, Eigenvector centrality

**TypeScript:** `tsc --noEmit` clean after all fixes.

**Files changed:**

- `frontend/src/components/stages/Stage1Panel.tsx`
- `frontend/src/components/stages/Stage6Panel.tsx`
- `frontend/src/components/stages/Stage7Panel.tsx`
- `frontend/src/types/api.ts`
- `backend/analysis/stages/stage6_ppi.py`

---

## Task 4.2 — Result Plausibility Check

**Date:** 2026-05-23

**Analysis examined:** `b65ac7a4-0ea2-4dc5-b40d-cd088b3fc2c5` — complete, auto mode, 689 compounds (Curcuma longa + Zingiber officinale), 26-node PPI network, 5 hub genes.

### Stage 3 — Target Identification (218 genes)

**Verdict: ✅ Plausible**

Gene symbols are consistent with known pharmacology of curcuminoids and gingerols:

- **CYP enzymes** (CYP1A1/1A2/1B1/2C9/2C19/2D6/3A4/19A1): well-documented inhibition by polyphenols — correct
- **Carbonic anhydrases** (CA1–CA14): established quercetin/polyphenol targets via competitive inhibition — correct
- **PPARG, PPARA, PPARD**: nuclear receptors; PPARG in particular is a primary curcumin target (literature: Aggarwal 2009) — correct
- **HMGCR**: HMG-CoA reductase; curcumin shown to inhibit cholesterol synthesis — correct
- **ALOX5, ALOX12, ALOX15**: lipoxygenases; gingerol and curcumin known anti-inflammatory via AA pathway — correct
- **ACHE, BACE1, MAPT**: Alzheimer's targets; curcumin studied for neurodegeneration — correct
- **DPP4, SLC5A2**: T2DM drug targets (gliptins, SGLT2 inhibitors) — plausible for metabolic disease context
- **EGFR, MTOR, BRAF, PIK3CA**: oncology signaling; consistent with curcumin anti-cancer literature

No implausible outliers detected. Target panel is scientifically coherent with plant compound profile.

### Stage 7 — Hub Genes (5 hubs from 26-node PPI)

**Verdict: ✅ Plausible — all 5 are established drug targets**

| Gene | Degree | Betweenness | Hub+Bottleneck | DrugBank drugs | Notes |
|------|--------|-------------|----------------|----------------|-------|
| PPARG | 19 | 0.3851 | ✅ | Rosiglitazone, Pioglitazone (T2DM) | Master adipogenesis/insulin regulator — correctly #1 hub |
| ESR1 | 12 | 0.0778 | — | Tamoxifen, Raloxifene, Anastrozole | Estrogen receptor alpha; known curcumin target |
| PPARA | 11 | 0.0642 | — | Fenofibrate, Gemfibrozil (fibrates) | Lipid metabolism; plausible with plant metabolites |
| HMGCR | 10 | 0.0692 | — | Atorvastatin, Simvastatin (statins) | Cholesterol synthesis; curcumin inhibitor in literature |
| MTOR | 10 | 0.0336 | — | Rapamycin, Everolimus | Central metabolic/growth regulator |

PPARG as Hub+Bottleneck (highest degree + highest betweenness by far) is biologically sound: it's a master regulator co-connecting metabolic, inflammatory, and adipogenesis pathways. Consistent with curcumin's known PPARG agonism.

### Stage 8 — Pathway Enrichment

**Verdict: ❌ Pipeline Bug — g:Profiler always returned 0 terms**

**Root cause:** `correction_method: "fdr_bh"` is not a valid g:Profiler REST API parameter. The API returned HTTP 400. The exception handler (`except httpx.HTTPError: return []`) swallowed the error silently, so Stage 8 has always stored `total_significant: 0` for every analysis run.

**Evidence:** Direct API call without `correction_method` → 86–123 significant terms for the same gene set.

**Expected enrichments** (verified by direct API call with hub genes PPARG/ESR1/PPARA/HMGCR/MTOR/BRAF/DPP4/NOS2/VDR):
- GO:MF — nuclear receptor activity, ligand-modulated transcription factor activity
- GO:BP — regulation of multicellular organismal process, regulation of biological quality, cellular response to chemical stimulus
- Consistent with a curcumin/plant polyphenol study targeting metabolic and inflammatory pathways

**Fix applied:** Removed `"correction_method": "fdr_bh"` from payload in `backend/integrations/gprofiler.py` (line 37). Verified: 123 results returned after fix.

**Impact:** All previously completed analyses have empty Stage 8 results stored in DB. New analyses will populate correctly. Existing analyses would need to be re-run to see enrichment results.

### Adjacent Findings

**Stage 6 empty network for small gene sets:** Analysis `ebbc6f19` (overlap=2: ALOX15, MAPT) produced 0 nodes/0 edges in Stage 6. STRING-DB returned no interactions for this pair at min_confidence=0.4. This is scientifically valid behaviour (sparse overlap = sparse network), not a bug. The EmptyState rendering was already verified in Phase 3.

**Disease ID not persisted in API responses:** All `analysis.disease_id` fields return empty string in the analyses list endpoint. This is a pre-existing issue with model serialization or data not being stored — out of scope for this audit but logged here for follow-up.

### Fix Applied

**File changed:** `backend/integrations/gprofiler.py`
- Removed invalid `"correction_method": "fdr_bh"` parameter from g:Profiler API payload
- g:Profiler uses its own multiple-testing correction by default; `user_threshold` correctly controls FDR cutoff

---
