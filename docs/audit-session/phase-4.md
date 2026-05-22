# Phase 4 — Scientific/Academic Soundness Audit

## Task 4.1 — Methodology Transparency Checklist

**Date:** 2026-05-23

### Checklist Results

| Stage | Required disclosure | Status | Evidence |
|-------|---------------------|--------|---------|
| 1 | Data source (KNApSAcK) | ❌ → ✅ Fixed | No footnote existed — added KNApSAcK Core disclosure |
| 2 | Lipinski RO5 + Veber rules | ✅ | Lines 161–162: full criteria with numeric bounds |
| 2 | NP exception explained | ✅ | Lines 163–165: explains structural complexity rationale |
| 3 | Source = ChEMBL, threshold = pChEMBL ≥ 5.0 | ✅ | Lines 96–97: "Source: ChEMBL … pChEMBL ≥ 5.0 (≡ IC₅₀ ≤ 10µM)" |
| 4 | Source = Open Targets, score meaning 0–1 | ✅ | Lines 77–82: "Open Targets score (0–1): overall disease–gene association strength" |
| 5 | Fisher's exact test p-value label | ✅ | StatCard label="Fisher's Exact p-value" |
| 5 | Warning if overlap = 0 | ✅ | Warning block lines 96–104 with downstream validity alert |
| 6 | Source = STRING-DB, min_confidence stated | ❌ → ✅ Fixed | Static text "set in analysis parameters" replaced with live `{result.min_confidence}` value |
| 6 | Hub criterion = degree > µ + σ | ✅ | Line 225: "overlap gene with degree > µ + σ (mean + 1 SD)" |
| 7 | 4 centrality metric definitions available | ❌ → ✅ Fixed | Added third disclosure paragraph defining Degree/Betweenness/Closeness/Eigenvector |
| 7 | Hub+Bottleneck criterion explained | ✅ | Lines 108–110: "gene exceeding BOTH degree and betweenness thresholds" |
| 8 | x-axis = -log₁₀(FDR) confirmed | ✅ | XAxis label `'-log₁₀(FDR)'` (line 54) |
| 8 | Reference line at FDR = 0.05 | ✅ | `ReferenceLine x={1.301}` (-log₁₀(0.05) = 1.301) |
| 8 | GO:BP/MF/CC spelled out | ✅ | `SOURCE_LABELS` map: "GO: Biological Process", "GO: Molecular Function", "GO: Cellular Component" |
| 8 | Method = g:Profiler ORA noted | ✅ | Lines 148–150: "Method: g:Profiler ORA (over-representation analysis)" |

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

*(Pending — see below)*

---
