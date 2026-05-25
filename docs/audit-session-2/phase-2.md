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
| T2.6 | Data Sources collapsible per stage | ✅ Complete | `112d2b9` |
| T2.7 | Fuzzy search + disease display names | ✅ Complete | pending |
| T2.8 | DataTable pagination | ✅ Complete | pending |

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

---

## T2.6 — Data Sources Attribution Per Stage

**Commit**: `112d2b9`

Added `DataSources.tsx` shared collapsible component to all 8 stage panels. Each stage shows its data sources with external links. Stage8 had a naming conflict (`SOURCES` already used for pathway sources) — resolved by renaming the new constant to `DATA_SOURCES_MAP`.

**Files**: `shared/DataSources.tsx` (new), all 8 `Stage*Panel.tsx`

---

## T2.7 — Fuzzy Search + Disease Display Names

**Commit**: pending

### Fuzzy search
- Installed `fuse.js 7.3.0`
- `PlantSelector`: disabled cmdk built-in filter (`shouldFilter={false}`), added `query` state controlled on `CommandInput`, fuse.js searches `canonical_scientific_name` + `family_name` at threshold 0.4
- `DiseaseSelector`: same pattern, searches `disease_name` + `ontology_id`
- Query resets on popover close

### Disease display names
- `src/lib/format.ts` → `formatDiseaseName(name)`: title-cases each word, preserves 2+ consecutive uppercase acronyms (HIV, COVID, DNA…), keeps minor words (of, the, a, an, in, on, for, with, by, and, or, but, via…) lowercase unless first word
- Applied in `DiseaseSelector` for both trigger label and dropdown items

**Files**: `src/lib/format.ts` (new), `PlantSelector.tsx`, `DiseaseSelector.tsx`

---

## Phase 2 Summary

---

## T2.8 — DataTable Pagination

**Commit**: pending

Replaced the "Show all N rows" toggle with proper pagination controls in `DataTable`.

- **Page size selector**: 10 / 25 / 50 / All pills — pill for selected size gets `font-medium` + border; others borderless
- **Row range indicator**: `rangeStart–rangeEnd of total` (e.g. "1–25 of 119"); tabular-nums for stable layout
- **Prev/Next navigation**: `ChevronLeft`/`ChevronRight` (lucide-react); disabled + opacity-30 when at boundary; only shown when `totalPages > 1`
- **Auto-reset to page 1** via `useEffect` when filter or sort changes — prevents stale pages after narrowing results
- `pageSize` prop retained for initial selection; clamped to valid options (10/25/50); default changed 50 → 25
- Footer only renders when `totalRows > 0` (avoids empty row below empty table)
- Test updated: `DataTable.test.tsx` replaces "Show all" assertion with range indicator + aria-label button assertions

**Files**: `shared/DataTable.tsx`, `tests/unit/DataTable.test.tsx`

---

## Phase 2 Summary

**8 tasks complete. 102 tests passing (68 backend + 34 frontend).**

| Task | Bugs / Features | Key files |
|------|----------------|-----------|
| T2.1 | Skeleton UX | Stage*Panel.tsx × 8, SkeletonTable.tsx |
| T2.2 | Cache invalidation fix | useAnalysisStatus.ts |
| T2.3 | Delete confirmation | PipelineSidebar.tsx |
| T2.4 | TTL + expiry enforcement + banner | analysis_repo.py, PipelinePage.tsx |
| T2.5 | Reset-from + redo button | analysis_repo.py, analyses.py, PipelinePage.tsx |
| T2.6 | Data sources collapsible per stage | shared/DataSources.tsx, Stage*Panel.tsx × 8 |
| T2.7 | Fuzzy search + disease title-case | format.ts, PlantSelector.tsx, DiseaseSelector.tsx |
| T2.8 | DataTable pagination | DataTable.tsx, DataTable.test.tsx |
