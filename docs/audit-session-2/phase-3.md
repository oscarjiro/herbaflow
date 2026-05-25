# Phase 3: In-Stage Params + Target Editing

**Status**: ✅ Complete  
**Spec**: `.superpowers/plans/2026-05-25-herbaflow-audit-2.md` Phase 3

---

## Summary

| Task | Status | Description | Commit |
|------|--------|-------------|--------|
| T3.1 | ✅ Complete | In-stage params panel with Rerun Stage button | 39a850e |
| T3.2 | ✅ Complete | Next-stage params preview in ApprovalBar | ca771cd |
| T3.3 | ✅ Complete | Target add/remove (Stage 3 + Stage 4) | 291ec2d–90d6a2c |

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

---

## T3.2 — Next-Stage Params Preview in ApprovalBar

### What Was Built

**Configure Next Stage** section added to `ApprovalBar` in guided mode. When Stage N is awaiting approval, users can view and edit the next stage's pipeline parameters before approving. Edits are submitted alongside the approval — the backend applies them before starting Stage N+1.

**Backend changes:**
- `ApproveRequest` Pydantic schema added (`param_overrides: dict | None`)
- `merge_run_parameters()` repository function added — deep-merges dict values, replaces scalars
- `POST /analyses/{id}/approve` extended to accept optional `ApproveRequest` body; calls `merge_run_parameters` before triggering next stage

**Frontend changes:**
- `ApproveRequest` interface added to `api.ts`
- `api.approveStage()` updated to accept optional `ApproveRequest` body
- `useApproveStage` hook extended to forward `param_overrides` from call site
- `ApprovalBar` rewritten: collapsible **Configure Next Stage** section using `StageParamsPanel` in edit-only mode; approval calls `approveStage({ param_overrides })` with current values

### Files Changed

**Backend:**
- `backend/app/schemas/analysis.py` — added `ApproveRequest`
- `backend/app/repositories/analysis_repo.py` — `merge_run_parameters()`
- `backend/app/routers/analyses.py` — extended approve endpoint

**Frontend:**
- `frontend/src/types/api.ts` — `ApproveRequest`
- `frontend/src/lib/api.ts` — `approveStage` body param
- `frontend/src/hooks/useApproveStage.ts` — updated mutation
- `frontend/src/components/shared/ApprovalBar.tsx` — Configure Next Stage UI

---

## T3.3 — User Target Add/Remove (Stage 3 + Stage 4)

### What Was Built

Users can add and remove protein targets from Stage 3 (compound targets) and Stage 4 (disease targets) results. All adds require UniProt validation (human proteins only, taxon 9606). Mutations operate on `stage_results` JSON only — no CompoundTarget/DiseaseTarget DB rows. Validated `Target` rows are upserted as permanent canonical cache. After any mutation, a stale banner prompts the user to rerun Stages 5–8 via the existing `reset-from/5` endpoint.

**Backend changes:**
- `backend/integrations/uniprot.py` (new) — async UniProt REST client: accession lookup + gene symbol search; taxon 9606 hard-check; user-facing `ValueError` on failure; wraps `httpx.HTTPError` and `HTTPStatusError`
- `AddUserTargetRequest` / `AddUserTargetResponse` Pydantic schemas added to `analysis.py`
- `_add_target_to_stage3` / `_remove_target_from_stage3` pure helpers in `analyses.py`: deep-copy, case-insensitive duplicate detection, `user_modified: True` flag, immutable inputs
- `_add_target_to_stage4` / `_remove_target_from_stage4` pure helpers: same pattern; Stage 4 user targets get `association_score: 1.0`
- `POST /analyses/{id}/targets/user` (201): validate → upsert Target → mutate stage_3 JSON → persist
- `DELETE /analyses/{id}/targets/{gene_symbol}` (204): remove from stage_3 JSON → persist
- `POST /analyses/{id}/disease-targets/user` (201): same pattern for stage_4
- `DELETE /analyses/{id}/disease-targets/{gene_symbol}` (204): same pattern for stage_4
- 23 new unit tests covering all 4 helpers (TDD, immutability, case-insensitivity, error codes)

**Frontend changes:**
- `user_modified?: boolean` added to `Stage3Result` and `Stage4Result` in `api.ts`
- `AddUserTargetRequest` / `AddUserTargetResponse` types added
- 4 API methods: `addUserTarget`, `removeUserTarget`, `addUserDiseaseTarget`, `removeUserDiseaseTarget`
- 4 TanStack Query mutation hooks: `useAddUserTarget`, `useRemoveUserTarget`, `useAddUserDiseaseTarget`, `useRemoveUserDiseaseTarget`
- `AddTargetForm` shared component: text input + submit button, loading/error states, `hf-*` tokens
- `Stage3Panel` rewritten: columns defined inside component (closure over remove mutation), stale banner, `＋ Add Target` form, ✕ remove button per row, `user_provided` source badge
- `Stage4Panel` rewritten: same pattern; filters by `['gene_symbol', 'disease_name']`

**Key decisions:**
- No CompoundTarget/DiseaseTarget DB rows for user targets (no molecular evidence)
- Target rows ARE persisted permanently (canonical UniProt cache)
- Stage 4 user targets get `association_score: 1.0` (user asserting clinical relevance)
- Any target removable (not only user-added)
- Stale signal: `user_modified: true` in stage result JSON → banner + manual rerun

### Commits

| Commit | Description |
|--------|-------------|
| 291ec2d | UniProt client + Stage 3 helpers + tests |
| 8d20932 | Stage 3 add/remove endpoints |
| 9768f1c | Stage 4 helpers + endpoints + tests |
| 100f556 | Frontend types, API methods, 4 hooks |
| 1836fba | AddTargetForm shared component |
| 9cfe8b8 | Stage3Panel rewrite with add/remove UI |
| 90d6a2c | Stage4Panel rewrite with add/remove UI |

### Tests

- 23 new backend unit tests (11 Stage 3 helpers + 12 Stage 4 helpers), all TDD
- 101 backend tests pass total; 34 frontend tests pass; TypeScript clean

### Files Changed

**Backend:**
- `backend/integrations/uniprot.py` — new UniProt REST client
- `backend/app/schemas/analysis.py` — `AddUserTargetRequest`, `AddUserTargetResponse`
- `backend/app/routers/analyses.py` — 4 helpers + 4 endpoints
- `backend/tests/unit/test_add_user_target.py` — Stage 3 helper tests
- `backend/tests/unit/test_add_user_disease_target.py` — Stage 4 helper tests

**Frontend:**
- `frontend/src/types/api.ts` — types updated
- `frontend/src/lib/api.ts` — 4 new API methods
- `frontend/src/hooks/useAddUserTarget.ts` — new
- `frontend/src/hooks/useRemoveUserTarget.ts` — new
- `frontend/src/hooks/useAddUserDiseaseTarget.ts` — new
- `frontend/src/hooks/useRemoveUserDiseaseTarget.ts` — new
- `frontend/src/components/shared/AddTargetForm.tsx` — new
- `frontend/src/components/stages/Stage3Panel.tsx` — rewritten
- `frontend/src/components/stages/Stage4Panel.tsx` — rewritten
