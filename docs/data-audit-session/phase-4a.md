# Phase 4-A: Network Pharmacology Stages 1-5 Review

## Executive Summary

Audit of Stages 1-5: Compound selection, ADME filtering, ChEMBL targets, disease targets, overlap analysis.
- **3 user decisions required** before Phase 5 fixes
- **1 critical bug found**: disease_id never persisted in AnalysisRun

## Stage 1: Compound Selection

### Deduplication
✅ **PRESENT** - List comprehension in line 25 auto-deduplicates. Each compound appears once in output with full plant list.

---

## Stage 2: ADME Filter

### PAINS Filter
✅ **CONFIRMED NON-FUNCTIONAL (intentional)** - apply_pains hardcoded False, never used in filter_compounds() logic. PAINS flag preserved for reporting only.

---

## Stage 3: ChEMBL Target Query

### pChEMBL Threshold
✅ **5.0 µM applied** - backend/integrations/chembl.py:60-61 filters `pchembl < 5.0`

### Assay Confidence Score
⚠️ **MISSING FILTER** - ChEMBL assay_confidence_score (0-9) field completely ignored
- Code captures only pchembl_value, target_chembl_id, target_organism, assay_type
- No filtering on assay quality (direct vs indirect/cell-based)
- Recommendation: Add min_assay_confidence >= 7 parameter

**DECISION GATE 1 REQUIRED**: Implement assay confidence filtering?

### Target Organism Filter
✅ **ENFORCED** - human_only=True always, API passes "target_organism": "Homo sapiens"

### Gene Deduplication
✅ **PRESENT** - Dictionary keyed by gene_symbol, set() removes duplicate compound-target pairs

---

## Stage 4: Disease Target Sources

### CRITICAL BUG: disease_id NOT PERSISTED

**Finding**: backend/app/routers/analyses.py:41 creates run WITHOUT disease_id FK
- Line 39: disease_ids injected into parameters["_disease_ids"] ONLY
- create_run() receives: (session, name, mode, parameters) — no disease_id argument
- Result: AnalysisRun.disease_id = NULL in all 87 rows (Phase 0 verified)

**Root Cause**: API payload plural (disease_ids list), schema field singular (disease_id FK). Router never persists FK.

**DECISION GATE 2 REQUIRED**: Single or multiple diseases per analysis?
- Option A (RECOMMENDED): Remove disease_id FK, keep parameters["_disease_ids"] (multiple diseases)
- Option B: Populate disease_id in router (single disease only)

### Disease Target Retrieval
✅ **FALLBACK PATTERN CONFIRMED**
- Primary: Query database disease_targets table (cached from ETL)
- Fallback: Open Targets API if no database rows

### Association Score Threshold
✅ **0.3 applied** - disease_repo.py:34 filters `score >= min_score`

### Empty disease_ids Handling
🟡 **SILENT FAILURE RISK** - If disease_ids empty, returns empty targets list silently with no error flag

**DECISION GATE 3 REQUIRED**: Make disease_ids mandatory?

---

## Stage 5: Target Overlap Statistics

### Jaccard Index
✅ **CORRECT** - overlap_count / union_count = |A∩B| / |A∪B|

### Hypergeometric Test
✅ **CORRECT** - All parameters verified:
- M=20,000 (Homo sapiens protein-coding genes) ✅
- scipy.stats.hypergeom used correctly ✅
- One-tailed test (survival function) ✅

---

## Summary

| Item | Status | Decision Gate |
|------|--------|----------------|
| Stage 1: Deduplication | ✅ | None |
| Stage 2: PAINS | ✅ | None |
| Stage 3: pChEMBL | ✅ | None |
| Stage 3: Assay Confidence | ⚠️ MISSING | **Gate 1** |
| Stage 3: Human Filter | ✅ | None |
| Stage 4: disease_id FK | 🔴 NULL | **Gate 2** |
| Stage 4: Empty disease_ids | 🟡 Silent | **Gate 3** |
| Stage 4: Association Score | ✅ | None |
| Stage 5: Jaccard | ✅ | None |
| Stage 5: Hypergeom | ✅ | None |

---

## Decision Gates

### Gate 1: Assay Confidence Score Filtering
**Current**: All pChEMBL >= 5.0 included regardless of assay quality
**Proposal**: Add min_assay_confidence >= 7 filter (excludes indirect/cell-based)
**Impact**: May drop 20-40% of targets
**Question**: Implement?

### Gate 2: disease_id Architecture
**Current**: AnalysisRun.disease_id always NULL, disease list in parameters only
**Proposal**: Option A = remove FK (support multiple diseases); Option B = populate FK (single disease)
**Question**: Single or multiple diseases per analysis?

### Gate 3: Empty disease_ids Validation
**Current**: Empty disease_ids returns zero targets silently
**Proposal**: Reject empty disease_ids in router validation
**Question**: Make disease_ids mandatory?

---

**Report complete. Awaiting user confirmation on Gates 1-3 before Phase 5-B implementation.**
