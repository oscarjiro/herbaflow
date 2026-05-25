# Audit Session 2 — Phase 2: UX Improvements

**Date**: 2026-05-25  
**Goal**: Improve pipeline UX — loading feedback, auto-mode bug fix, new-analysis confirmation, analysis TTL, and redo-step button.

---

## Tasks

| Task | Title | Status | Commit |
|------|-------|--------|--------|
| T2.1 | Skeleton loading states for running stages | ✅ Complete | `d34d996` |
| T2.2 | Auto mode UX bug — stale stage results cache | ✅ Complete | `3043eb7` |
| T2.3 | Analysis clear confirmation dialog | ✅ Complete | `0d38ac0` |
| T2.4 | Analysis TTL 24h expiry | ✅ Complete | `55844e7` |
| T2.5 | Redo Step button with reset-from endpoint | ✅ Complete | `9d04977` |
| T2.6 | Data Sources collapsible per stage | 🔲 Next | — |
| T2.7 | Fuzzy search + disease display names | 🔲 Pending | — |
| T2.8 | DataTable pagination | 🔲 Pending | — |

---

## T2.1 — Skeleton Loading States

**Commit**: `d34d996`

Added animated skeleton loaders during pipeline execution. Behavior:
- `stage_N_running` → animated gray skeleton bars (SkeletonTable component)
- `stage_N_awaiting_approval` → real results rendered normally

**Files**: `PipelinePage.tsx`, all 8 `Stage*Panel.tsx`, `shared/SkeletonTable.tsx` (new)

---

## T2.2 — Auto Mode Cache Fix

**Commit**: `3043eb7`

**Root cause**: `useAnalysisStatus` polling detected status changes but didn't invalidate `useAnalysis` cache, leaving stage content stale in auto mode.

**Fix**: `queryClient.invalidateQueries(['analysis', id])` on every status change (not just terminal states).

**Files**: `frontend/src/hooks/useAnalysisStatus.ts`

---

## T2.3 — Analysis Clear Confirmation Dialog

**Commit**: `0d38ac0`

Added Radix `AlertDialog` to "New Analysis" button in `PipelineSidebar`. On confirm: `DELETE /analyses/{id}` → navigate to SetupPage. Backend `DELETE` already cascades to all child records — no backend changes.

**Files**: `frontend/src/components/pipeline/PipelineSidebar.tsx`

---

## T2.4 — Analysis TTL 24h Expiry

**Commit**: `55844e7`

### Backend
- Migration: `ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS expires_at timestamptz`
- `update_run_status()`: sets `expires_at = NOW() + 24h` on completion
- `GET /analyses/{id}`: returns `410 Gone` if expired
- `GET /analyses/{id}/status`: exposes `expires_at`

### Frontend
- `formatExpiryTime(ms)` helper renders countdown
- Warning banner when < 2h remaining
- 410 error → "Analysis Expired" state

**Files**: `analysis_repo.py`, `analyses.py` (router), `schemas/`, `api.ts`, `PipelinePage.tsx`, `docs/database.md`

---

## T2.5 — Redo Step Button + Reset-From Endpoint

**Commit**: `9d04977`

### Backend
- `reset_run_from_stage(run_id, stage)`: clears stage_results ≥ N, resets status to `stage_{N-1}_awaiting_approval` (or `pending` if N=1), nulls `completed_at`/`expires_at`/`error_message`
- `POST /analyses/{id}/reset-from/{stage}`: validates stage 1–8; fires pipeline background task if stage=1
- `ResetResponse` schema: `{ run_id, stage_reset_from, new_status }`

### Frontend
- `api.resetFromStage(id, stage)` typed wrapper
- `useResetFromStage` TanStack Query mutation; invalidates analysis + status queries on success
- "Redo Stage N" button in `StagePanelRouter` (guided mode only, shown when stage has results)
- Radix Dialog confirmation before mutation fires

### Also fixed
- `expires_at` migration was committed but not applied to live Supabase DB — applied via MCP; fixed 9 test failures

**Files**: `analysis_repo.py`, `analyses.py` (router), `api.ts`, `useResetFromStage.ts` (new), `PipelinePage.tsx`

---

## Phase 2 Summary

**5 tasks complete. 5 commits on main. 102 tests passing (68 backend + 34 frontend).**

| Task | Bugs / Features | Key files |
|------|----------------|-----------|
| T2.1 | Skeleton UX | Stage*Panel.tsx × 8, SkeletonTable.tsx |
| T2.2 | Cache invalidation fix | useAnalysisStatus.ts |
| T2.3 | Delete confirmation | PipelineSidebar.tsx |
| T2.4 | TTL + expiry enforcement + banner | analysis_repo.py, PipelinePage.tsx |
| T2.5 | Reset-from + redo button | analysis_repo.py, analyses.py, PipelinePage.tsx |
