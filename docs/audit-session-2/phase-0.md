# Audit Session 2 — Phase 0: Scientific Audit & Fixes

**Date**: 2026-05-25  
**Goal**: Verify scientific correctness of all 8 pipeline stages against published methodology; fix any bugs or misalignments found.

---

## T0.1 — Stage 2 ADME Screening

**Status**: ✅ Complete  
**Files touched**: `backend/analysis/stages/stage2_adme.py`, `frontend/src/components/stages/Stage2Panel.tsx`

### Scientific Methodology Verified

| Rule | Implementation | Standard | Status |
|------|----------------|----------|--------|
| Lipinski MW ≤ 500 Da | `c.molecular_weight > params.max_mw` | Lipinski et al. 2001 | ✅ |
| Lipinski LogP ≤ 5 | `c.logp > params.max_logp` | Lipinski et al. 2001 | ✅ |
| Lipinski HBD ≤ 5 | `c.hbond_donors > params.max_hbd` | Lipinski et al. 2001 | ✅ |
| Lipinski HBA ≤ 10 | `c.hbond_acceptors > params.max_hba` | Lipinski et al. 2001 | ✅ |
| Veber TPSA ≤ 140 Å² | `c.tpsa > params.max_tpsa` (gated by `apply_veber`) | Veber et al. 2002 | ✅ |
| Veber rotbonds ≤ 10 | `c.rotatable_bonds > params.max_rotatable_bonds` | Veber et al. 2002 | ✅ |
| NP exception | `np_likeness_score ≥ params.np_exception_threshold` | Ertl & Roggo 2008 | ✅ |
| PAINS | Flag only — `is_pains_positive` column, no filter | Baell & Holloway 2010 | ✅ |

**Citations**:
- Lipinski CA et al. (2001). *Experimental and computational approaches to estimate solubility and permeability in drug discovery and development settings.* Adv Drug Deliv Rev 46:3–26.
- Veber DF et al. (2002). *Molecular properties that influence the oral bioavailability of drug candidates.* J Med Chem 45:2615–2623.
- Ertl P, Roggo S (2008). *Natural product-likeness score and its application for prioritization of compound libraries.* J Chem Inf Model 48:68–74.
- Baell JB, Holloway GA (2010). *New substructure filters for removal of pan assay interference compounds from screening libraries.* J Med Chem 53:2719–2740.

### Bugs Found & Fixed

**Bug 1 — Backend: ADME fields missing from stage output** (root cause of empty columns)  
`stage2_adme.py` lines 87–96: `enriched` list built only `compound_id`, `canonical_name`, `plant_ids`, `adme_pass`, `is_np_exception`, `is_pains_positive` — omitting all 7 ADME numeric properties. Frontend `AdmeCompoundResult` type correctly declared all fields; they simply weren't populated.  
Fix: Added `molecular_weight`, `logp`, `tpsa`, `hbond_donors`, `hbond_acceptors`, `np_likeness_score`, `rotatable_bonds` to enriched dict.

**Bug 2 — Frontend: NP exception shows "Fail" in Result column**  
NP exception compounds have `adme_pass: false` (failed Lipinski/Veber) but `is_np_exception: true` — they're passed through to Stage 3 via `all_active_compound_ids`. The Result column rendered them as "Fail" (red), which contradicts their active status.  
Fix: Result column render now checks `row.is_np_exception` first → shows "Pass (NP)" (amber badge).

**Bug 3 — Frontend: Filter "Passed" excluded NP exceptions; "Failed" included them**  
Filter mode logic treated `!adme_pass` as failed, putting NP exceptions in the failed bucket. Also `total` excluded `np_exceptions` from denominator, making percentages not sum to 100%.  
Fix: "Passed" filter → `adme_pass || is_np_exception`; "Failed" filter → `!adme_pass && !is_np_exception`; `total` includes `np_exceptions`.

### No Issues Found

- `apply_pains` parameter documented as no-op (PAINS state comes from ETL, not re-computed here) — intentional, correctly handled as flag-only in UI.
- NP exception threshold is user-configurable via `AdmeParams.np_exception_threshold` — defensible.
- All null checks present for optional ADME fields.

---

---

## T0.2 — Stage 3 Target Identification

**Status**: ✅ Complete  
**Files touched**: `frontend/src/types/api.ts`, `frontend/src/components/stages/Stage3Panel.tsx`

### Scientific Methodology Verified

| Parameter | Implementation | Standard | Status |
|-----------|----------------|----------|--------|
| pChEMBL ≥ 5.0 | API param `assay_confidence_score__gte` + client-side filter | IC₅₀ ≤ 10µM standard (Srivastava 2020) | ✅ |
| Human only | `target_organism=Homo sapiens` in ChEMBL query | Standard for human disease NP research | ✅ |
| Assay confidence ≥ 7 | `min_assay_confidence=7` default | ChEMBL confidence ≥6 is standard; 7 is more stringent (ChEMBL docs) | ✅ |
| UniProt accession | `syn_type=="UNIPROT"` from target_component_synonyms | Returns bare accession (e.g. P02794), not protein name | ✅ |

**Citations**:
- Srivastava V et al. (2020). *Network pharmacology-based identification of key pharmacological pathways of Yin-Huang-Ke-Li.* Front Pharmacol 11:1491.
- ChEMBL documentation: assay_confidence_score scale 0–9; ≥6 = directaly-assigned protein target, ≥7 = curated single-protein target.

### Bugs Found & Fixed

**Bug 1 — Frontend: `coverage_percent` vs `coverage_pct` field name mismatch**  
Backend `stage3_targets.py` returns `coverage_pct` (renamed in prior audit). `Stage3Result` TypeScript type and `Stage3Panel.tsx` template both still used `coverage_percent` → Coverage StatCard always showed 0.0%.  
Fix: Updated `Stage3Result.coverage_percent` → `coverage_pct` in `api.ts`; updated template reference.

### Minor Improvements

- `compound_count` column header renamed to "Binding Compounds" — more precise: counts compounds that bind to that target, not all compounds in the analysis.

### No Issues Found

- UniProt accession rendering is correct — plan concern was based on wrong assumption about field content.
- `min_assay_confidence=7` (default) is more stringent than the ≥6 minimum, which is scientifically conservative and defensible.
- Coverage calculation uses correct denominator: `len(compound_ids)` (all active compounds from Stage 2).

---

*Further tasks: T0.3 (Stage 4), T0.4 (Stage 5), T0.5 (Stage 6), T0.6 (Stage 7), T0.7 (Stage 8), T0.8 (misc)*
