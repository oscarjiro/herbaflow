# Phase 3: In-Stage Params + Target Editing

**Status**: In Progress  
**Spec**: `.superpowers/plans/2026-05-25-herbaflow-audit-2.md` Phase 3

---

## Summary

| Task | Status | Description | Commit |
|------|--------|-------------|--------|
| T3.1 | ✅ Complete | In-stage params panel with Rerun Stage button | TBD |
| T3.2 | ⏳ Pending | Next-stage params preview in ApprovalBar | — |
| T3.3 | ⏳ Pending | Target add/remove (Stage 3 + Stage 4) | — |

---

## T3.1 — In-Stage Params Panel

### What Was Built

Collapsible **Stage Parameters** section added above results in Stage 2, 3, 4, 6, 7, and 8 panels. Shows all current pipeline config params (editable inline). Includes **Rerun Stage N** button (guided mode only) that saves new params to `run.parameters` and immediately reruns the stage via reset-from with `rerun: true`.

**Backend changes:**
- `ResetFromRequest` Pydantic schema added (`params: dict | None`, `rerun: bool = False`)
- `reset_run_from_stage()` extended with optional `param_overrides` — deep-merges dict values into `run.parameters` before clearing stage results
- `POST /analyses/{id}/reset-from/{stage}` now accepts optional JSON body; `rerun=true` triggers `run_stage()` as background task for stage > 1

**Frontend changes:**
- `ResetFromRequest` + 6 param config types added to `api.ts`
- `api.resetFromStage()` updated to accept optional body
- `useResetFromStage` hook: mutationFn now takes `{stage, body?}`
- `PipelinePage` Redo dialog updated to new hook signature
- New `StageParamsPanel` shared component: collapsible, stage-aware, editable number/boolean/multi-select fields, Rerun button
- Stage 2–4, 6–8 panels: `StageParamsPanel` integrated above results section

**Stage → param key mapping:**
| Stage | Config Key | Editable Fields |
|-------|-----------|-----------------|
| 2 | `adme` | max_mw, max_logp, max_hbd, max_hba, max_tpsa, max_rotatable_bonds, np_exception_threshold, apply_veber, apply_pains |
| 3 | `target` | min_pchembl, human_only, min_assay_confidence |
| 4 | `disease_targets` | min_score |
| 6 | `ppi` | min_confidence |
| 7 | `hub_genes` | top_n, use_hub_bottleneck |
| 8 | `enrichment` | fdr_threshold, sources (GO:BP/GO:MF/GO:CC/KEGG toggle) |

Stages 1 and 5 have no params panel (no configurable params).

### Tests

- 19 new backend unit tests in `backend/tests/unit/test_reset_from.py` covering param merge logic and repo function
- 79/79 backend tests pass; 34/34 frontend tests pass; TypeScript clean

### Files Changed

**Backend:**
- `backend/app/schemas/analysis.py` — added `ResetFromRequest`
- `backend/app/repositories/analysis_repo.py` — `reset_run_from_stage` with `param_overrides`
- `backend/app/routers/analyses.py` — extended reset-from endpoint
- `backend/tests/unit/test_reset_from.py` — 19 new unit tests

**Frontend:**
- `frontend/src/types/api.ts` — param config types + `ResetFromRequest`
- `frontend/src/lib/api.ts` — `resetFromStage` body param
- `frontend/src/hooks/useResetFromStage.ts` — updated mutation signature
- `frontend/src/pages/PipelinePage.tsx` — Redo dialog call updated
- `frontend/src/components/shared/StageParamsPanel.tsx` — **new file**
- `frontend/src/components/stages/Stage2Panel.tsx` — StageParamsPanel integrated
- `frontend/src/components/stages/Stage3Panel.tsx` — StageParamsPanel integrated
- `frontend/src/components/stages/Stage4Panel.tsx` — StageParamsPanel integrated
- `frontend/src/components/stages/Stage6Panel.tsx` — StageParamsPanel integrated
- `frontend/src/components/stages/Stage7Panel.tsx` — StageParamsPanel integrated
- `frontend/src/components/stages/Stage8Panel.tsx` — StageParamsPanel integrated
