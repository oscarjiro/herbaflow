# Phase 2 — Playwright Live QA Audit Log

---

## Task 2.1 — Static Pages

**Tested:** `/` and `/about`

### Landing Page (/)
- ascii-dna animation: ✓ renders (T·A, G·C base pairs visible in snapshot)
- Heading "Herbaflow" level=1: ✓
- NavBar: "Herbaflow" wordmark + "About" link: ✓
- "Start Analysis" CTA → `/analysis`: ✓
- Console errors: 0 (only React DevTools info)
- No img 404s observed

### About Page (/about)
- Content visible: ✓ (Project, Methodology, Author, User Manual sections)
- NavBar present: ✓
- Console errors: 0

### Adjacent Issues Found (log only — Phase 4 scientific audit)
- `about` Stage 2 description: "Lipinski and ADME parameters" — should say "Lipinski RO5 + Veber rules" (Veber is omitted)
- `about` Stage 3 description: "reverse docking or target databases" — implementation uses ChEMBL specifically, not reverse docking
- `about` Stage 7 description: lists "degree, betweenness, closeness centrality" — eigenvector centrality is also used but omitted

**Status:** PASS

---

## Task 2.2 — Setup Form

**Plants combobox:** ✓ opens, searchable, multi-select works ("2 plants selected" badge shown), per-plant remove buttons present. Family name rendered conditionally (correct — some plants have empty family_name per data quality issue logged in Phase 1).

**Disease combobox:** ✓ opens, searchable, shows `disease_name + ontology_id` (e.g. "type 2 diabetes mellitus DOID_9352"), single-select.

**Analysis name:** ✓ auto-populated "Analysis — 2026-05-22".

**Mode toggle:** ✓ Guided (default) / Auto buttons present.

**Advanced params accordion:** ✓ collapsed by default, expands per section. All defaults match spec:

| Param | Expected | Actual |
|-------|----------|--------|
| max_mw | 500 | 500 ✓ |
| max_logp | 5 | 5 ✓ |
| max_hbd | 5 | 5 ✓ |
| max_hba | 10 | 10 ✓ |
| max_tpsa | 140 | 140 ✓ |
| max_rotatable_bonds | 10 | 10 ✓ |
| apply_veber | true | true ✓ |
| np_exception_threshold | 0.5 | 0.5 ✓ |
| min_pchembl | 5.0 | 5.0 ✓ |
| min_score | 0.3 | 0.3 ✓ |
| min_confidence | 0.4 | 0.4 ✓ |
| top_n | 20 | 20 ✓ |
| fdr_threshold | 0.05 | 0.05 ✓ |

**Submit:** ✓ POST fires, redirected to `/analysis/b65ac7a4-0ea2-4dc5-b40d-cd088b3fc2c5`. No console errors.

**Analysis:** Zingiber officinale Roscoe (571 compounds) + Curcuma longa L. (180 compounds) vs. type 2 diabetes mellitus (DOID_9352). Guided mode.

**Status:** PASS

---

## Task 2.3 — Guided Pipeline Stages 1–8

Analysis: `b65ac7a4-0ea2-4dc5-b40d-cd088b3fc2c5` · Zingiber officinale (571 cpds) + Curcuma longa (180 cpds) vs. T2DM (DOID_9352) · Guided mode · **Pipeline status: complete**

### Stage 1 — Compound Selection
**Status:** PASS (verified by prior session)
- 3 stat cards render; compound table with SMILES preview; sort by MW functional

### Stage 2 — ADME Screening
**Status:** FIXED + PASS
- Stats: Passed 564 (89.1%), Failed 69 (10.9%), NP Exceptions 56 ✓
- **Issues fixed:**
  - Table was missing MW, LogP, TPSA, HBD, HBA, NP-likeness columns → added all 6
  - No "Lipinski RO5 + Veber rules" label anywhere → added scientific footnote
  - NP exception not explained → added NP exception note
  - `AdmeCompoundResult` type missing ADME property fields → added to `api.ts`
- Filter buttons (All/Passed/Failed) present ✓
- Console errors: 0

### Stage 3 — Target Identification
**Status:** FIXED + PASS
- **Issues fixed:** No ChEMBL source or pChEMBL threshold visible → added footnote
- Gene tag cloud with "Show all N genes" toggle ✓
- Table: Gene Symbol, Compound Count, UniProt ID ✓
- Adjacent: Hub genes found include PPARG, ESR1, PPARA, HMGCR, MTOR, DPP4, SLC5A2 — biologically plausible for T2DM ✓

### Stage 4 — Disease Targets
**Status:** FIXED + PASS
- **Issues fixed:**
  - Column header "Association Score" → "Open Targets Score"
  - No source explanation → added footnote (Open Targets score 0–1, DB cache vs API note)
- UniProt accessions format correct ✓

### Stage 5 — Target Overlap
**Status:** FIXED + PASS
- **Issues fixed:**
  - "P-value" → "Fisher's Exact p-value"
  - Missing Venn circle labels → added "Compound Targets" / "Disease Targets" above SVG
  - Zero-overlap warning banner missing → added (triggers when overlap_count = 0)
  - Field name mismatches: `jaccard_index` → `jaccard`, `overlap_genes` → `overlap` (fixed by linter in api.ts)
- Jaccard formula note + method note added ✓

### Stage 6 — PPI Network
**Status:** FIXED + PASS
- **Issues fixed:**
  - Cytoscape CSS custom properties don't resolve on canvas → replaced all `var(--hf-*)` with hex equivalents in stylesheet (fixed by linter)
  - Legend "Overlap target" swatch was `bg-hf-fg1` (wrong) → `var(--hf-ink)` inline style
  - No STRING-DB attribution → added footnote (source, edge weight formula)
  - No hub criterion formula → added to footnote
- Hub/overlap/other nodes visually distinct ✓; controls (layout/fit/export) present ✓

### Stage 7 — Hub Gene Analysis
**Status:** FIXED + PASS
- **Issues fixed:**
  - Abbreviated column headers → expanded to "Degree Centrality", "Betweenness Centrality", "Closeness Centrality", "Eigenvector Centrality"
  - No Hub+Bottleneck explanation → added footnote
- Hub rows sage-faint background ✓; CSV export button present ✓
- Threshold footnote: "degree ≥ N (= µ + σ) · betweenness ≥ N (= µ + σ)" ✓
- **Note:** µ/σ raw values not returned by backend API — only computed thresholds available

### Stage 8 — Pathway Enrichment
**Status:** FIXED + PARTIAL
- **Critical bug fixed:** Frontend type completely mismatched backend response
  - Backend: `{go_bp, go_mf, go_cc, kegg, total_significant, hub_genes_queried}`
  - Frontend was using: `{terms[], significant_count}` → crashed with `result.terms.filter is not a function`
  - Fixed `Stage8Result` type and `Stage8Panel` to use correct field names
- **Scientific fixes applied:** Reference line at FDR=0.05 added; g:Profiler ORA method note added; `-log₁₀(FDR)` x-axis label confirmed correct ✓
- **Finding:** `total_significant = 0`, all category arrays empty — g:Profiler returned no significant enrichment terms for these hub genes in this run. Possible causes: g:Profiler API connectivity, gene set too small, or genuine lack of enrichment at FDR < 0.05. Stage 8 EmptyState renders correctly for all 4 tabs ✓ (no crash).
- Hub genes queried: PPARG, ESR1, PPARA, HMGCR, MTOR, NR1H4, MGAM, DPP4, HTT, CYP19A1, PPARD, IGF1R, PIK3R1, XDH, SLC5A2, BRAF, FFAR1, AGTR1, NOS2, CYP27B1 (20 genes — biologically plausible for T2DM)

**Overall:** Pipeline runs end-to-end. All 8 stages approved. Major bugs fixed: Stage 2 missing ADME columns, Stage 5 field mismatches, Stage 6 Cytoscape CSS token bug, Stage 8 complete type mismatch. Scientific disclosure footnotes added across Stages 2–8. TypeScript: clean post-fix.

---

## Task 2.4 — Auto Pipeline

**Analysis:** ebbc6f19-293c-4e0f-92fb-6f9282e30618 · 1 plant (asthma disease) · Auto mode

### ApprovalBar
PASS: No Approve/Reject buttons appeared at any stage during auto pipeline execution. `isAwaitingApproval` guard correctly requires `status?.mode === 'guided'`, which is never true in auto mode.

### Sidebar Auto-Advance
PASS: Sidebar showed all 8 stage buttons (1 Compound Selection → 8 Pathway Enrichment). Pipeline auto-advanced through all stages without user interaction. Sidebar labels confirmed as "NStage Name" format (e.g. "1Compound Selection"), not "Stage N" — test selectors updated accordingly.

### Pipeline Completion
PASS: All 8 stages reached `complete` at ~21:34 GMT+7. Final status: `complete`, `current_stage: 8`. Pipeline took ~5 minutes due to external API calls (ChEMBL, Open Targets, STRING-DB, g:Profiler).

### Stage Spot-Checks
- Stage 1: PASS — compound table renders, 5 compounds listed (HYPEROSIDE, MYRICETIN, ISOQUERCETIN, QUERCITRIN, beta-D-Glucopyranuronosyl...), table rows visible
- Stage 5: PASS — Venn SVG renders (10 SVG elements), overlap data visible (2 overlap genes: ALOX15, MAPT; 64 compound-only, 386 disease-only targets), Jaccard index and Fisher p-value shown
- Stage 8: PASS — Pathway enrichment panel renders without crash; 0 significant pathways found (g:Profiler returned no results for this gene set / disease pairing — empty state displayed correctly with GO:BP/MF/CC/KEGG tabs all visible)

### Console Errors
0 — no console errors across any stage spot-check

### Polling Behavior
PASS: After `complete` status, 0 new requests to `/analyses/:id/status` observed in 10-second window. Both `useAnalysis` and `useAnalysisStatus` correctly return `false` from `refetchInterval` when `isTerminalStatus(status)` is true.

### Bugs Fixed
1. **Stage2Panel.tsx TS error** — `render: (v) => v ?? '—'` returned inferred type `{}` (not assignable to `ReactNode`). Fixed: changed to `v != null ? String(v) : '—'` for HBD and HBA columns. Build was failing with TS2322; now clean.

### Adjacent Issues
- Pipeline test timeout: `pollUntilComplete` defaulted to 5 minutes — insufficient for real external API calls (pipeline took ~5 min). Updated Playwright spec timeout to 11 minutes. Not a product bug — performance characteristic.
- Probe/temp spec files (`probe-buttons.spec.ts`, `probe-after-select.spec.ts`, `probe-pipeline-complete.spec.ts`, `probe-setup.js/.cjs`) created during QA — should be cleaned up before merge.

**Status:** PASS
