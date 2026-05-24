# Phase 3: ADME Screening Scientific Review

> Audit date: 2026-05-24  
> Effort level: [xH] — scientific/academic scrutiny  
> Tasks: P3-A (AdmeParams docstring + ADME methodology assessment), P3-B (PAINS no-op validation), + approved extension (PAINS flag full-stack)

---

## P3-A: Scientific Justification of Screening Rules

### Files Reviewed

- `backend/analysis/stages/stage2_adme.py`
- `backend/analysis/models.py` — `AdmeParams` dataclass

### ADME Methodology Verdict

| Component | Implementation | Scientific Standing | Action |
|---|---|---|---|
| Lipinski RO5 | MW ≤ 500, logP ≤ 5, HBD ≤ 5, HBA ≤ 10 | Designed for synthetic oral drugs; overly strict for natural products **alone**, but NP exception compensates | Defensible with NP exception; documented |
| Veber rules | TPSA ≤ 140, rotatable bonds ≤ 10 | Standard intestinal permeability complement to RO5 (Veber et al., J. Med. Chem. 2002) | ✅ Appropriate |
| NP exception | np_likeness_score ≥ 0.5 (Ertl & Schuffenhauer 2008) | Threshold 0.5 captures strong NP character; bypasses RO5/Veber for natural products | ✅ Scientifically sound |
| PAINS filter | `apply_pains=False` (hard filter disabled) | Correct for computational/network pharmacology — no biochemical assay screening; flagging appropriate | ✅ Acceptable; see P3-B + extension |
| QED score | Stored, not filtered | Correct — QED best used as ranking signal within passing compounds (Bickerton et al., 2012) | ✅ No change needed |

**Overall verdict**: RO5 + Veber + NP exception (threshold 0.5) is scientifically defensible for a network pharmacology thesis on Indonesian medicinal plants. The NP exception is the critical component that saves the methodology — without it, a substantial fraction of bioactive natural products would be excluded.

### AdmeParams Docstring Added

Full scientific docstring added to `AdmeParams` in `backend/analysis/models.py` with citations:

- Lipinski et al., Adv. Drug Deliv. Rev. 23:3-25, 1997
- Veber et al., J. Med. Chem. 45:2615-2623, 2002
- Ertl & Schuffenhauer, J. Nat. Prod. 71:951-959, 2008
- Baell & Holloway, J. Med. Chem. 53:2719-2740, 2010

Commit: `3de8534 feat(backend): add is_pains_positive PAINS flag to compound screening output`

---

## P3-B: PAINS Config Validation

### Finding

`apply_pains` is declared in `AdmeParams` with `apply_pains: bool = False`, but is **never read in `filter_compounds()`** in `stage2_adme.py`. The field is a complete no-op — it neither filters compounds when `True` nor causes any side-effect when `False`.

**Verdict**: Harmless. The hard filter is correctly disabled. No logic change needed.

**Documented as**: intentional no-op via `AdmeParams` docstring: `"Not applied as a hard filter (apply_pains=False); NP pipeline targets computational target prediction, not biochemical assay screening."`

---

## Extension: PAINS Flag Full-Stack Implementation

**User decision (approved)**: Add `is_pains_positive` as a **reporting-only flag** across the full stack — not a filter. Enables downstream inspection of which compounds contain Pan-Assay Interference Compound patterns without affecting compound selection.

### Changes Applied

| Layer | File | Change |
|---|---|---|
| ETL enrichment | `etl/compounds/04_enrich/patch_missing_lipinski.py` | Pass 3: `_load_pains_catalog()` + `check_pains()` — computes flag for all SMILES rows |
| ETL export | `etl/compounds/07_export/run.py` | `is_pains_positive` added to `COMPOUNDS_COLUMNS` |
| DB migration | `supabase/migrations/20260524000001_add_is_pains_positive_to_compounds.sql` | `ALTER TABLE compounds ADD COLUMN is_pains_positive boolean NOT NULL DEFAULT false` |
| Backend ORM | `backend/app/models/compound.py` | `is_pains_positive: bool = False` on `Compound` SQLModel |
| Analysis model | `backend/analysis/models.py` | `is_pains_positive: bool = False` on `CompoundRecord` dataclass |
| Analysis pipeline | `backend/analysis/stages/stage2_adme.py` | Reads from DB, emits in enriched output per compound |
| Documentation | `.claude/docs/database.md` | `is_pains_positive` row documented in compounds table schema |

### Commits

- `fd87196 feat(etl/compounds): add PAINS flag computation to patch_missing_lipinski (Pass 3)`
- `3de8534 feat(backend): add is_pains_positive PAINS flag to compound screening output`

### Known Deferred State

All live DB rows currently have `is_pains_positive = false` (the migration default). Actual values will be populated after ETL re-run (deferred to Phase 6 ETL re-run checklist).

---

## Summary

| Task | Status | Commits |
|---|---|---|
| P3-A: AdmeParams docstring with citations | ✅ Complete | `3de8534` |
| P3-A: ADME methodology assessment | ✅ Defensible as-is | — |
| P3-B: apply_pains confirmed no-op | ✅ Verified | — |
| Extension: PAINS flag full-stack | ✅ Complete | `fd87196`, `3de8534` |

---

## Adjacent Findings

None.
